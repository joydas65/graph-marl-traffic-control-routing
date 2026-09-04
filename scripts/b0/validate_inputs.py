#!/usr/bin/env python3
"""Validate and freeze the local-only B0 network, demand, and disruption inputs."""

from __future__ import annotations

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import sumolib


INPUT_DIR = Path("inputs")
CHECK_DIR = Path("checks")
NETWORK = INPUT_DIR / "b0-grid-3x3.net.xml"
ROUTES = INPUT_DIR / "b0-fixed-routes.rou.xml"
DEMAND_MANIFEST = INPUT_DIR / "demand-manifest.json"
DISRUPTION = INPUT_DIR / "disruption-specification.json"
PREFLIGHT_OUTPUT = CHECK_DIR / "preflight.json"
TLS_OUTPUT = CHECK_DIR / "tls-programs.json"
HASH_OUTPUT = CHECK_DIR / "input-sha256.json"
EXPECTED_TLS = {f"{column}{row}" for column in "ABC" for row in range(3)}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_once(path: Path, value: object) -> None:
    if path.exists():
        raise AssertionError(f"refusing to overwrite {path.as_posix()}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    CHECK_DIR.mkdir(parents=True, exist_ok=True)
    require(not PREFLIGHT_OUTPUT.exists(), "preflight was already recorded")

    network = sumolib.net.readNet(str(NETWORK), withPrograms=True)
    tls_by_id = {tls.getID(): tls for tls in network.getTrafficLights()}
    require(set(tls_by_id) == EXPECTED_TLS, "expected exactly nine grid TLS IDs")

    tls_records: dict[str, object] = {}
    for tls_id, tls in sorted(tls_by_id.items()):
        programs = tls.getPrograms()
        require(set(programs) == {"0"}, f"unexpected TLS programs for {tls_id}")
        program = programs["0"]
        require(program.getType() == "static", f"non-static TLS program at {tls_id}")
        phases = [
            {"duration_seconds": phase.duration, "state": phase.state}
            for phase in program.getPhases()
        ]
        require(len(phases) >= 2, f"insufficient phases at {tls_id}")
        tls_records[tls_id] = {
            "program_id": "0",
            "type": program.getType(),
            "phases": phases,
        }

    regular_edges = [edge for edge in network.getEdges() if not edge.isSpecial()]
    internal_edges = [
        edge
        for edge in regular_edges
        if edge.getFromNode().getID() in EXPECTED_TLS
        and edge.getToNode().getID() in EXPECTED_TLS
    ]
    physical_zones = {
        tuple(sorted((edge.getFromNode().getID(), edge.getToNode().getID())))
        for edge in internal_edges
    }
    require(len(physical_zones) == 12, "expected twelve internal physical zones")
    require(len(internal_edges) == 24, "expected two directed edges per physical zone")
    require(
        all(len(edge.getLanes()) == 2 for edge in regular_edges),
        "every regular directed edge must have two lanes",
    )
    require(
        all(lane.allows("passenger") for edge in regular_edges for lane in edge.getLanes()),
        "every regular lane must initially permit passenger vehicles",
    )

    route_root = ET.parse(ROUTES).getroot()
    require(not route_root.findall("trip"), "runtime-routed trip elements are forbidden")
    require(not route_root.findall("flow"), "flow elements are forbidden")
    require(not route_root.findall("rerouter"), "rerouter elements are forbidden")
    route_defs = {
        node.attrib["id"]: node.attrib["edges"].split()
        for node in route_root.findall("route")
    }
    vehicles = route_root.findall("vehicle")
    require(len(route_defs) == 12, "expected twelve explicit routes")
    require(len(vehicles) == 180, "expected 180 explicit scheduled vehicles")
    vehicle_ids = [vehicle.attrib["id"] for vehicle in vehicles]
    require(len(set(vehicle_ids)) == len(vehicle_ids), "duplicate vehicle ID")
    require(all("route" in vehicle.attrib for vehicle in vehicles), "inline routing is forbidden")
    departures = [float(vehicle.attrib["depart"]) for vehicle in vehicles]
    require(min(departures) >= 0 and max(departures) < 900, "departure outside frozen window")
    route_counts = Counter(vehicle.attrib["route"] for vehicle in vehicles)
    require(set(route_counts.values()) == {15}, "expected fifteen vehicles per route")

    covered_directed_internal_edges: set[str] = set()
    route_tls_counts: dict[str, int] = {}
    for route_id, edge_ids in route_defs.items():
        require(len(edge_ids) == 4, f"route {route_id} must contain four directed edges")
        route_edges = [network.getEdge(edge_id) for edge_id in edge_ids]
        for current, following in zip(route_edges, route_edges[1:]):
            require(
                following in current.getOutgoing(),
                f"disconnected edge sequence in route {route_id}",
            )
        traversed_tls = {
            node_id
            for edge in route_edges
            for node_id in (edge.getFromNode().getID(), edge.getToNode().getID())
            if node_id in EXPECTED_TLS
        }
        require(len(traversed_tls) == 3, f"route {route_id} must traverse three TLS nodes")
        route_tls_counts[route_id] = len(traversed_tls)
        covered_directed_internal_edges.update(
            edge.getID() for edge in route_edges if edge in internal_edges
        )
    require(
        covered_directed_internal_edges == {edge.getID() for edge in internal_edges},
        "frozen routes must cover every directed internal edge",
    )

    demand_manifest = json.loads(DEMAND_MANIFEST.read_text(encoding="utf-8"))
    require(demand_manifest["scenario_seed"] == 20260904, "seed mismatch")
    require(demand_manifest["scheduled_trip_count"] == 180, "manifest count mismatch")
    require(demand_manifest["routes_fixed_before_simulation"] is True, "routes not frozen")
    require(demand_manifest["dynamic_rerouting"] is False, "rerouting enabled")

    disruption = json.loads(DISRUPTION.read_text(encoding="utf-8"))
    require(disruption["directed_edge_id"] == "A1B1", "unexpected disrupted edge")
    require(disruption["lane_id"] == "A1B1_0", "unexpected disrupted lane")
    require(disruption["remaining_route_feasible_lane_id"] == "A1B1_1", "unexpected remaining lane")
    disrupted_edge = network.getEdge(disruption["directed_edge_id"])
    closed_lane = network.getLane(disruption["lane_id"])
    remaining_lane = network.getLane(disruption["remaining_route_feasible_lane_id"])
    require(len(disrupted_edge.getLanes()) == 2, "disrupted edge is not two-lane")
    require(closed_lane.allows("passenger"), "selected lane is not passenger-usable")
    require(remaining_lane.allows("passenger"), "remaining lane is not passenger-usable")
    require(
        "left1A1_1" in {lane.getID() for lane in remaining_lane.getIncoming()},
        "remaining lane lacks exposed-route predecessor connection",
    )
    require(
        "B1C1_1" in {connection.getToLane().getID() for connection in remaining_lane.getOutgoing()},
        "remaining lane lacks exposed-route successor connection",
    )
    require(
        "B1C1_0" in {connection.getToLane().getID() for connection in closed_lane.getOutgoing()},
        "closed lane does not carry the exposed straight route",
    )
    exposed = [
        trip for trip in demand_manifest["scheduled_trips"]
        if disruption["directed_edge_id"] in trip["edges"]
    ]
    require(len(exposed) == 15, "unexpected structural exposure count")
    require(
        sum(300 <= trip["scheduled_departure_seconds"] < 600 for trip in exposed) == 5,
        "no frozen exposed demand during the event window",
    )
    require(
        math.isclose(disruption["scheduled_route_exposure_fraction"], 15 / 180),
        "exposure fraction mismatch",
    )

    input_paths = sorted(
        path for path in INPUT_DIR.iterdir()
        if path.is_file() and path.name != HASH_OUTPUT.name
    )
    input_hashes = {path.as_posix(): sha256(path) for path in input_paths}

    write_json_once(TLS_OUTPUT, tls_records)
    write_json_once(HASH_OUTPUT, {"sha256": input_hashes})
    write_json_once(
        PREFLIGHT_OUTPUT,
        {
            "status": "PASS",
            "controlled_intersection_count": len(tls_by_id),
            "static_tls_programs": True,
            "regular_directed_edge_count": len(regular_edges),
            "internal_directed_edge_count": len(internal_edges),
            "eligible_physical_disruption_zone_count": len(physical_zones),
            "explicit_route_count": len(route_defs),
            "scheduled_trip_count": len(vehicles),
            "route_counts": dict(sorted(route_counts.items())),
            "route_tls_counts": route_tls_counts,
            "all_internal_directed_edges_covered": True,
            "selected_lane_initially_passenger_usable": True,
            "remaining_lane_route_feasibility_validated": True,
            "scheduled_routes_structurally_exposed": len(exposed),
            "scheduled_exposed_departures_during_event": 5,
            "dynamic_rerouting": False,
        },
    )


if __name__ == "__main__":
    main()
