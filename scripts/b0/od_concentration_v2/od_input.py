"""Frozen B0 OD allocation, validation and XML serialization; no simulator or writes.

Read the contract only via an explicit load_contract(path) call. All other
operations consume supplied data and return immutable trips, bytes, or reports.
The logical digest binds assignments independently of XML formatting.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Mapping, Sequence
import xml.etree.ElementTree as ET


ADAPTER_IDENTITY = "B0_OD_INPUT_ADAPTER_V1"
CONTRACT_SHA256 = "a450405a7e14ea7c099edb7bf9cd8598b72b3d392444c08c8ba481e96902284b"
CONTRACT_LOGICAL_SHA256 = "6e572708a869d23a1b323985ed915ef36d3e7a1094570c2161dcb57afd04dd0a"


@dataclass(frozen=True)
class Trip:
    vehicle_id: str
    scheduled_departure_seconds: int
    route_id: str


def _digest(value: Any, *, sort_keys: bool = False) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, sort_keys=sort_keys, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _checked_contract(contract: Mapping[str, Any]) -> Mapping[str, Any]:
    # Prevent mutation of a previously loaded dict from revising the frozen design.
    if _digest(contract, sort_keys=True) != CONTRACT_LOGICAL_SHA256:
        raise ValueError("contract content differs from the frozen OD design")
    return contract


def load_contract(path: str | Path) -> dict[str, Any]:
    """Read only the explicit file and verify its exact frozen byte identity."""
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("contract byte identity differs from the frozen design")
    contract = json.loads(raw)
    _checked_contract(contract)
    return contract


def _level(contract: Mapping[str, Any], seed: int, level: str) -> Mapping[str, Any]:
    _checked_contract(contract)
    if type(seed) is not int or seed not in contract["calibration_seeds"]:
        raise ValueError("seed is outside the three frozen calibration seeds")
    for candidate in contract["concentration"]["ladder"]:
        if type(level) is str and candidate["label"] == level:
            return candidate
    raise ValueError("concentration is outside the frozen C1-C4 ladder")


def build_seed_allocations(
    contract: Mapping[str, Any], seed: int
) -> dict[str, tuple[Trip, ...]]:
    """Generate all four concentrations from the same fifteen permutations."""
    _level(contract, seed, "C1")
    rng = random.Random(seed)
    permutations = []
    for _ in range(15):
        permutation = list(range(36))
        rng.shuffle(permutation)
        permutations.append(permutation)
    residual = contract["allocation"]["residual_route_order"]
    allocations = {}
    for candidate in contract["concentration"]["ladder"]:
        target_per_block = candidate["target_route_trips"] // 15
        residual_index = 0
        trips = []
        for block, permutation in enumerate(permutations):
            routes_by_slot = [""] * 36
            for rank, slot in enumerate(permutation):
                if rank < target_per_block:
                    route = "row1_east"
                else:
                    route = residual[residual_index % 11]
                    residual_index += 1
                routes_by_slot[slot] = route
            for slot, route in enumerate(routes_by_slot):
                trips.append(Trip(
                    f"veh_{36 * block + slot:04d}",
                    60 * block + (5 * slot) // 3,
                    route,
                ))
        result = tuple(trips)
        validate_allocation(contract, seed, candidate["label"], result)
        allocations[candidate["label"]] = result
    return allocations


def validate_allocation(
    contract: Mapping[str, Any], seed: int, level: str, trips: Sequence[Trip]
) -> dict[str, Any]:
    """Check the frozen table/digests without regenerating expected assignments."""
    candidate = _level(contract, seed, level)
    if len(trips) != 540:
        raise ValueError("allocation must contain exactly 540 trips")
    route_order = contract["allocation"]["canonical_route_order"]
    schedule, assignments = [], []
    for index, trip in enumerate(trips):
        if not isinstance(trip, Trip):
            raise ValueError("allocation contains a non-Trip record")
        block, slot = divmod(index, 36)
        if (trip.vehicle_id != f"veh_{index:04d}"
                or type(trip.scheduled_departure_seconds) is not int
                or trip.scheduled_departure_seconds != 60 * block + 5 * slot // 3):
            raise ValueError("vehicle ID, ordering or departure vector differs")
        if trip.route_id not in route_order:
            raise ValueError("vehicle references an unknown route")
        schedule.append([trip.vehicle_id, trip.scheduled_departure_seconds])
        assignments.append([*schedule[-1], trip.route_id])
    totals = Counter(trip.route_id for trip in trips)
    if totals != candidate["per_route_totals"]:
        raise ValueError("route totals differ from the frozen table")
    block_targets = []
    for block in range(15):
        counts = Counter(trip.route_id for trip in trips[36 * block:36 * (block + 1)])
        residual_counts = [counts[r] for r in contract["allocation"]["residual_route_order"]]
        if set(counts) != set(route_order) or max(residual_counts) - min(residual_counts) > 1:
            raise ValueError("within-block route representation or balance differs")
        block_targets.append(counts["row1_east"])
    if block_targets != candidate["target_trips_per_block"]:
        raise ValueError("target counts per block differ")
    schedule_digest, assignment_digest = _digest(schedule), _digest(assignments)
    oracle = contract["offline_validation"]
    if schedule_digest != oracle["id_departure_vector_sha256"]:
        raise ValueError("schedule digest differs")
    reference = next(r for r in oracle["seed_reference_vectors"] if r["seed"] == seed)
    if assignment_digest != reference["new_logical_assignment_sha256"][level]:
        raise ValueError("logical assignment digest differs from the frozen oracle")
    return {
        "adapter_identity": ADAPTER_IDENTITY,
        "contract_sha256": CONTRACT_SHA256,
        "seed": seed, "level": level, "scheduled_trips": 540,
        "per_route_totals": {r: totals[r] for r in route_order},
        "target_trips_per_block": block_targets,
        "id_departure_vector_sha256": schedule_digest,
        "logical_assignment_sha256": assignment_digest,
    }


def serialize_routes(
    contract: Mapping[str, Any], seed: int, level: str, trips: Sequence[Trip]
) -> bytes:
    """Return deterministic fixed-route XML; persist it only through caller action."""
    validate_allocation(contract, seed, level, trips)
    config = contract["scientific_configuration"]
    root = ET.Element("routes")
    ET.SubElement(root, "vType", config["vehicle_type"])
    for definition in config["route_definitions"]:
        ET.SubElement(root, "route", definition)
    for trip in trips:
        ET.SubElement(root, "vehicle", {
            "id": trip.vehicle_id,
            "type": config["vehicle_attributes"]["type"],
            "route": trip.route_id,
            "depart": str(trip.scheduled_departure_seconds),
            "departLane": config["vehicle_attributes"]["departLane"],
            "departSpeed": config["vehicle_attributes"]["departSpeed"],
        })
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def validate_routes_xml(
    contract: Mapping[str, Any], seed: int, level: str, xml_bytes: bytes
) -> dict[str, Any]:
    """Validate structure and assignments; report XML and logical hashes separately."""
    _level(contract, seed, level)
    root = ET.fromstring(xml_bytes)
    config = contract["scientific_configuration"]
    children = list(root)
    expected_tags = ["vType"] + ["route"] * 12 + ["vehicle"] * 540
    if (root.tag != "routes" or root.attrib
            or [child.tag for child in children] != expected_tags
            or any(list(child) for child in children)):
        raise ValueError("XML contains changed structure, counts or nested routing")
    if any((node.text or "").strip() or (node.tail or "").strip() for node in root.iter()):
        raise ValueError("XML contains unexpected non-whitespace text")
    if children[0].attrib != config["vehicle_type"]:
        raise ValueError("vehicle type differs from the frozen definition")
    if [node.attrib for node in children[1:13]] != config["route_definitions"]:
        raise ValueError("route definitions or ordering differ")
    expected_attributes = {"id", "route", "depart", *config["vehicle_attributes"]}
    trips = []
    for node in children[13:]:
        attributes = node.attrib
        if set(attributes) != expected_attributes or any(
            attributes[key] != value for key, value in config["vehicle_attributes"].items()
        ):
            raise ValueError("vehicle attributes differ from the frozen definition")
        try:
            departure = int(attributes["depart"])
        except ValueError as error:
            raise ValueError("departure must be a canonical integer") from error
        if str(departure) != attributes["depart"]:
            raise ValueError("departure must be a canonical integer")
        trips.append(Trip(attributes["id"], departure, attributes["route"]))
    report = validate_allocation(contract, seed, level, trips)
    report["xml_sha256"] = hashlib.sha256(xml_bytes).hexdigest()
    return report


def paired_inputs(
    contract: Mapping[str, Any], seed: int, level: str, trips: Sequence[Trip]
) -> dict[str, bytes]:
    """N0/D0 reference the very same immutable bytes, with no condition edits."""
    raw = serialize_routes(contract, seed, level, trips)
    return {"N0": raw, "D0": raw}
