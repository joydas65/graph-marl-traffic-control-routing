#!/usr/bin/env python3
"""Run the isolated B0 per-vehicle exposure diagnostic exactly once."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import traceback
import types
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from exposure_observer import (
    OBSERVER_IDENTITY,
    ExposureObserver,
    ObservedConnection,
)


DIAGNOSTIC_IDENTITY = "B0_EXPOSURE_DIAGNOSTIC_V1"
EVIDENCE_IDENTITY = "b0-diagnostic/2026-09-04_seed-20260904/exposure-v1"
ORIGINAL_B0_IDENTITY = "b0/2026-09-04_seed-20260904"
EXPECTED_REPOSITORY_SHA = "2a0da664c8f43a1e346c3c405fbff3fc40a78778"
EXPECTED_ORIGINAL_RUNNER_SHA256 = (
    "d4286193089a8062ae16e51e3dbaf8f26df6be11d43399d6fd998941b275ccab"
)
SEED = 20260904
H_PILOT = 1500
STEP_SECONDS = 1.0
DISRUPTION_START = 300
DISRUPTION_END = 600
MONITORED_EDGE = "A1B1"
RESTRICTED_LANE = "A1B1_0"
SURVIVING_LANE = "A1B1_1"
PASSENGER_CLASS = "passenger"
RUN_ATTEMPT = 2

BUNDLE_ROOT = Path(__file__).resolve().parent
LOCAL_EVIDENCE_ROOT = BUNDLE_ROOT.parents[2]
ORIGINAL_ROOT = LOCAL_EVIDENCE_ROOT / "b0" / "2026-09-04_seed-20260904"
ORIGINAL_RUNNER_PATH = ORIGINAL_ROOT / "run_b0.py"
RUNNER_PATH = Path("run_b0_exposure_diagnostic.py")
OBSERVER_PATH = Path("exposure_observer.py")
ATTEMPT_CHECKS = Path("checks") / f"attempt-{RUN_ATTEMPT:03d}"
RUN_PLAN = (
    ("N0-DIAG", "N0", f"runs/n0-diag/attempt-{RUN_ATTEMPT:03d}", False),
    ("D0-DIAG", "D0", f"runs/d0-diag/attempt-{RUN_ATTEMPT:03d}", True),
    ("N0-DIAG-R", "N0-R", f"runs/n0-diag-r/attempt-{RUN_ATTEMPT:03d}", False),
    ("D0-DIAG-R", "D0-R", f"runs/d0-diag-r/attempt-{RUN_ATTEMPT:03d}", True),
)
ATTEMPT_INITIALIZED = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_text(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_once(path: Path, value: object) -> None:
    if path.exists():
        raise AssertionError(f"refusing to overwrite {path.as_posix()}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(json_text(value))
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def write_bytes_once(path: Path, value: bytes) -> None:
    if path.exists():
        raise AssertionError(f"refusing to overwrite {path.as_posix()}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("xb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def load_original_runner() -> types.ModuleType:
    """Load without SourceFileLoader so the frozen bundle gains no new pyc write."""

    source = ORIGINAL_RUNNER_PATH.read_bytes()
    actual_hash = hashlib.sha256(source).hexdigest()
    if actual_hash != EXPECTED_ORIGINAL_RUNNER_SHA256:
        raise AssertionError(
            "refusing to load an original B0 runner that differs from its receipt"
        )
    module = types.ModuleType("frozen_b0_runner_for_exposure_diagnostic")
    module.__file__ = str(ORIGINAL_RUNNER_PATH)
    module.__package__ = None
    exec(compile(source, str(ORIGINAL_RUNNER_PATH), "exec"), module.__dict__)
    return module


BASE = load_original_runner()


def configure_base_runner() -> None:
    BASE.SEED = SEED
    BASE.H_PILOT = H_PILOT
    BASE.STEP_SECONDS = STEP_SECONDS
    BASE.RUN_ATTEMPT = RUN_ATTEMPT
    BASE.DISRUPTION_START = DISRUPTION_START
    BASE.DISRUPTION_END = DISRUPTION_END
    BASE.DISRUPTED_EDGE_ID = MONITORED_EDGE
    BASE.DISRUPTED_LANE_ID = RESTRICTED_LANE
    BASE.REMAINING_LANE_ID = SURVIVING_LANE
    BASE.PASSENGER_CLASS = PASSENGER_CLASS
    BASE.INPUT_HASHES = Path("checks/input-sha256.json")
    BASE.DEMAND_MANIFEST = Path("inputs/demand-manifest.json")
    BASE.SCENARIO_MANIFEST = Path("inputs/scenario-manifest.json")
    BASE.DISRUPTION_MANIFEST = Path("inputs/disruption-specification.json")
    BASE.RUNNER_PATH = RUNNER_PATH
    BASE.EXPECTED_REPOSITORY_SHA = EXPECTED_REPOSITORY_SHA
    BASE.BUNDLE_ROOT = BUNDLE_ROOT
    BASE.RUN_PLAN = tuple((item[0], item[2], item[3]) for item in RUN_PLAN)
    BASE.ATTEMPT_CHECKS = ATTEMPT_CHECKS
    BASE.ATTEMPT_INITIALIZED = False


def tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def snapshot_digest(snapshot: Mapping[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def verify_frozen_inputs() -> dict[str, Any]:
    original_manifest = json.loads(
        (ORIGINAL_ROOT / "checks/input-sha256.json").read_text(encoding="utf-8")
    )["sha256"]
    diagnostic_manifest = json.loads(
        Path("checks/input-sha256.json").read_text(encoding="utf-8")
    )["sha256"]
    if original_manifest != diagnostic_manifest:
        raise AssertionError("diagnostic input-hash map differs from original B0")

    mismatches: dict[str, Any] = {}
    for identity, expected in sorted(original_manifest.items()):
        original_path = ORIGINAL_ROOT / identity
        diagnostic_path = Path(identity)
        original_actual = sha256(original_path)
        diagnostic_actual = sha256(diagnostic_path)
        if original_actual != expected or diagnostic_actual != expected:
            mismatches[identity] = {
                "expected": expected,
                "original_actual": original_actual,
                "diagnostic_actual": diagnostic_actual,
            }
    if mismatches:
        raise AssertionError(f"frozen B0 input mismatch: {mismatches}")

    if sha256(ORIGINAL_RUNNER_PATH) != EXPECTED_ORIGINAL_RUNNER_SHA256:
        raise AssertionError("original successful B0 runner no longer matches its receipt")

    scenario = json.loads(Path("inputs/scenario-manifest.json").read_text(encoding="utf-8"))
    disruption = json.loads(
        Path("inputs/disruption-specification.json").read_text(encoding="utf-8")
    )
    demand = json.loads(Path("inputs/demand-manifest.json").read_text(encoding="utf-8"))
    expected = {
        "scenario.network_id": (scenario.get("network_id"), "B0_GRID_3X3_V1"),
        "scenario.scenario_seed": (scenario.get("scenario_seed"), SEED),
        "scenario.simulation_start_seconds": (
            scenario.get("simulation_start_seconds"),
            0,
        ),
        "scenario.demand_end_seconds": (scenario.get("demand_end_seconds"), 900),
        "scenario.h_pilot_seconds": (scenario.get("h_pilot_seconds"), H_PILOT),
        "scenario.simulation_step_seconds": (
            scenario.get("simulation_step_seconds"),
            STEP_SECONDS,
        ),
        "scenario.fixed_time_signals": (scenario.get("fixed_time_signals"), True),
        "scenario.dynamic_rerouting": (scenario.get("dynamic_rerouting"), False),
        "scenario.conditions": (
            scenario.get("conditions_in_execution_order"),
            ["N0", "D0", "N0-R", "D0-R"],
        ),
        "disruption.edge": (disruption.get("directed_edge_id"), MONITORED_EDGE),
        "disruption.lane": (disruption.get("lane_id"), RESTRICTED_LANE),
        "disruption.surviving_lane": (
            disruption.get("remaining_route_feasible_lane_id"),
            SURVIVING_LANE,
        ),
        "disruption.start": (
            disruption.get("start_step_inclusive"),
            DISRUPTION_START,
        ),
        "disruption.end": (disruption.get("end_step_exclusive"), DISRUPTION_END),
        "disruption.vehicle_class": (
            disruption.get("vehicle_class_temporarily_disallowed"),
            PASSENGER_CLASS,
        ),
        "disruption.rerouting": (disruption.get("rerouting_permitted"), False),
        "demand.count": (demand.get("scheduled_trip_count"), 180),
        "demand.seed": (demand.get("scenario_seed"), SEED),
        "demand.fixed_routes": (demand.get("routes_fixed_before_simulation"), True),
    }
    contract_mismatches = {
        key: {"actual": actual, "expected": expected_value}
        for key, (actual, expected_value) in expected.items()
        if actual != expected_value
    }
    if contract_mismatches:
        raise AssertionError(f"frozen scientific contract mismatch: {contract_mismatches}")
    structural_trips = [
        item for item in demand["scheduled_trips"] if MONITORED_EDGE in item["edges"]
    ]
    structural_route_count_exceptions = {
        str(item["vehicle_id"]): list(item["edges"]).count(MONITORED_EDGE)
        for item in structural_trips
        if list(item["edges"]).count(MONITORED_EDGE) != 1
    }
    if len(structural_trips) != 15 or structural_route_count_exceptions:
        raise AssertionError(
            "frozen structural-exposure cohort does not traverse the monitored "
            "edge exactly once"
        )
    return {
        "status": "PASS",
        "diagnostic_identity": DIAGNOSTIC_IDENTITY,
        "original_b0_identity": ORIGINAL_B0_IDENTITY,
        "input_object_count": len(original_manifest),
        "sha256": dict(sorted(original_manifest.items())),
        "original_and_diagnostic_bytes_match": True,
        "frozen_scientific_contract_match": True,
        "frozen_structurally_exposed_vehicle_count": len(structural_trips),
        "frozen_structurally_exposed_vehicles_traverse_A1B1_exactly_once": True,
        "frozen_structural_route_count_exceptions": structural_route_count_exceptions,
        "original_runner_sha256": EXPECTED_ORIGINAL_RUNNER_SHA256,
    }


def attribute_call_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    return sorted(
        {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
    )


def verify_observer_noninterference_contract() -> dict[str, Any]:
    forbidden = {
        "changeLane",
        "changeLaneRelative",
        "rerouteEffort",
        "rerouteTraveltime",
        "setAllowed",
        "setDisallowed",
        "setPhase",
        "setPhaseDuration",
        "setProgram",
        "setRedYellowGreenState",
        "setRoute",
        "setRouteID",
        "setSpeed",
        "setType",
        "setVehicleClass",
    }
    required_reads = {
        "getAllowed",
        "getDisallowed",
        "getIDList",
        "getLaneID",
        "getLanePosition",
        "getRoadID",
        "getRouteIndex",
        "getSpeed",
        "getTime",
        "getVehicleClass",
    }
    observer_calls = set(attribute_call_names(OBSERVER_PATH))
    diagnostic_calls = set(attribute_call_names(RUNNER_PATH))
    original_calls = set(attribute_call_names(ORIGINAL_RUNNER_PATH))
    observer_forbidden = sorted(observer_calls & forbidden)
    diagnostic_forbidden = sorted(diagnostic_calls & forbidden)
    missing_reads = sorted(required_reads - observer_calls)
    original_control_calls = sorted(original_calls & forbidden)
    pass_contract = (
        not observer_forbidden
        and not diagnostic_forbidden
        and not missing_reads
        and original_control_calls == ["setAllowed", "setDisallowed"]
    )
    receipt = {
        "status": "PASS" if pass_contract else "FAIL",
        "observer_identity": OBSERVER_IDENTITY,
        "observer_forbidden_control_calls": observer_forbidden,
        "diagnostic_runner_forbidden_control_calls": diagnostic_forbidden,
        "required_read_calls_present": not missing_reads,
        "missing_required_read_calls": missing_reads,
        "original_runner_control_calls": original_control_calls,
        "original_runner_control_scope": (
            "Frozen restricted-lane permission activation/restoration only"
        ),
        "observer_advances_simulation_only_by_delegating_simulationStep": True,
        "observer_changes_vehicle_state": False,
        "observer_changes_routes": False,
        "observer_changes_tls": False,
        "observer_changes_lane_permissions": False,
    }
    if not pass_contract:
        raise AssertionError(f"observer non-interference contract failed: {receipt}")
    return receipt


def run_preflight_tests() -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_*.py",
        "-v",
    ]
    result = subprocess.run(
        command,
        cwd=BUNDLE_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    receipt = {
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "command": ["python3", *command[1:]],
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "sumo_executed": False,
    }
    if result.returncode != 0:
        raise AssertionError(f"pre-execution observer tests failed: {receipt}")
    return receipt


def run_observed_condition(
    *,
    run_id: str,
    output_identity: str,
    disrupted: bool,
    input_hashes: dict[str, str],
    demand: dict[str, Any],
    runner_hash: str,
    observer_hash: str,
    structural_ids: set[str],
) -> dict[str, Any]:
    observer = ExposureObserver(
        run_id=run_id,
        monitored_edges={MONITORED_EDGE: (RESTRICTED_LANE, SURVIVING_LANE)},
        passenger_class=PASSENGER_CLASS,
        event_start_seconds=DISRUPTION_START,
        event_end_seconds=DISRUPTION_END,
        pre_activation_time_seconds=DISRUPTION_START,
    )
    original_get_connection = BASE.traci.getConnection
    connection_requests = 0

    def observed_get_connection(label: str) -> ObservedConnection:
        nonlocal connection_requests
        connection_requests += 1
        return ObservedConnection(original_get_connection(label), observer)

    BASE.traci.getConnection = observed_get_connection
    run_dir = Path(output_identity)
    try:
        metrics = BASE.run_condition(
            run_id,
            output_identity,
            disrupted,
            input_hashes,
            demand,
            runner_hash,
        )
        if connection_requests < 1:
            raise AssertionError("diagnostic observer was never attached")
        observer.finalize(H_PILOT)
        if sha256(OBSERVER_PATH) != observer_hash:
            raise AssertionError("exposure observer changed during measured execution")
        write_json_once(run_dir / "exposure-events.json", observer.events_payload())
        write_json_once(
            run_dir / "pre-event-occupancy.json", observer.pre_activation_payload()
        )
        write_json_once(
            run_dir / "exposure-summary.json",
            observer.summary_payload(structural_ids),
        )
        return metrics
    except BaseException:
        if run_dir.exists():
            partial_path = run_dir / "partial-exposure-events.json"
            if not partial_path.exists():
                write_json_once(
                    partial_path,
                    {
                        "status": "PARTIAL_TECHNICAL_EVIDENCE",
                        "events": observer.events_payload(),
                        "pre_activation": (
                            None
                            if observer.pre_activation_states is None
                            else observer.pre_activation_payload()
                        ),
                    },
                )
        raise
    finally:
        BASE.traci.getConnection = original_get_connection


def parse_tripinfo_records(path: Path) -> dict[str, dict[str, float | None]]:
    records: dict[str, dict[str, float | None]] = {}
    for node in ET.parse(path).getroot().findall("tripinfo"):
        vehicle_id = str(node.attrib["id"])
        if vehicle_id in records:
            raise AssertionError(f"duplicate raw tripinfo ID {vehicle_id}")
        depart = float(node.attrib["depart"])
        arrival = float(node.attrib["arrival"])
        records[vehicle_id] = {
            "actual_departure_seconds": None if depart < 0 else depart,
            "arrival_seconds": None if arrival < 0 else arrival,
            "waiting_time_seconds": float(node.attrib["waitingTime"]),
        }
    return records


def nearest_rank_p95(values: list[float]) -> float:
    if not values:
        raise AssertionError("cannot compute P95 of an empty population")
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def raw_metric_recomputation(run_dir: Path, demand: dict[str, Any]) -> dict[str, Any]:
    scheduled = {
        str(item["vehicle_id"]): float(item["scheduled_departure_seconds"])
        for item in demand["scheduled_trips"]
    }
    tripinfo = parse_tripinfo_records(run_dir / "tripinfo.xml")
    if set(tripinfo) != set(scheduled):
        raise AssertionError(
            "raw tripinfo IDs do not exactly cover the scheduled population: "
            f"missing={sorted(set(scheduled) - set(tripinfo))}, "
            f"unknown={sorted(set(tripinfo) - set(scheduled))}"
        )
    arrivals = {
        vehicle_id
        for vehicle_id, record in tripinfo.items()
        if record["arrival_seconds"] is not None
    }
    restricted_times = [
        (
            float(H_PILOT)
            if tripinfo.get(vehicle_id, {}).get("arrival_seconds") is None
            else min(
                float(tripinfo[vehicle_id]["arrival_seconds"]),
                float(H_PILOT),
            )
        )
        - scheduled_departure
        for vehicle_id, scheduled_departure in sorted(scheduled.items())
    ]
    queue_burden = 0.0
    teleport_events = 0
    with (run_dir / "step-trace.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            queue_burden += (
                int(row["halting_vehicle_count_speed_below_0.1_mps"]) * STEP_SECONDS
            )
            teleport_events += int(row["starting_teleport_step_count"])
    waiting_total = sum(
        float(record["waiting_time_seconds"]) for record in tripinfo.values()
    )
    return {
        "scheduled_trips": len(scheduled),
        "arrivals": len(arrivals),
        "unfinished": len(scheduled) - len(arrivals),
        "teleport_events": teleport_events,
        "restricted_mean_trip_time_seconds": sum(restricted_times)
        / len(restricted_times),
        "restricted_p95_trip_time_seconds_nearest_rank": nearest_rank_p95(
            restricted_times
        ),
        "queue_burden_vehicle_seconds": queue_burden,
        "native_waiting_time_seconds": waiting_total,
    }


def canonical_xml_children(path: Path, child_tag: str) -> dict[str, Any]:
    def canonical(node: ET.Element) -> Any:
        return {
            "tag": node.tag,
            "attributes": dict(sorted(node.attrib.items())),
            "children": [canonical(child) for child in list(node)],
        }

    values: dict[str, Any] = {}
    for node in ET.parse(path).getroot().findall(child_tag):
        identity = node.attrib["id"]
        if identity in values:
            raise AssertionError(f"duplicate {child_tag} identity {identity}")
        values[identity] = canonical(node)
    return dict(sorted(values.items()))


def compare_scientific_run(
    diagnostic_run_dir: Path,
    original_run_dir: Path,
    diagnostic_metrics: dict[str, Any],
    demand: dict[str, Any],
) -> dict[str, Any]:
    diagnostic_raw = raw_metric_recomputation(diagnostic_run_dir, demand)
    original_raw = raw_metric_recomputation(original_run_dir, demand)
    raw_metrics_equal = diagnostic_raw == original_raw
    diagnostic_projection = BASE.scientific_metrics_projection(diagnostic_metrics)
    original_saved_metrics = json.loads(
        (original_run_dir / "final-metrics.json").read_text(encoding="utf-8")
    )
    aggregate_projection_equal = diagnostic_projection == BASE.scientific_metrics_projection(
        original_saved_metrics
    )
    checks = {
        "raw_metrics_equal": raw_metrics_equal,
        "step_trace_byte_equal": (diagnostic_run_dir / "step-trace.csv").read_bytes()
        == (original_run_dir / "step-trace.csv").read_bytes(),
        "vehicle_ledger_equal": json.loads(
            (diagnostic_run_dir / "vehicle-ledger.json").read_text(encoding="utf-8")
        )
        == json.loads(
            (original_run_dir / "vehicle-ledger.json").read_text(encoding="utf-8")
        ),
        "tripinfo_semantically_equal": canonical_xml_children(
            diagnostic_run_dir / "tripinfo.xml", "tripinfo"
        )
        == canonical_xml_children(original_run_dir / "tripinfo.xml", "tripinfo"),
        "vehroute_semantically_equal": canonical_xml_children(
            diagnostic_run_dir / "vehroute.xml", "vehicle"
        )
        == canonical_xml_children(original_run_dir / "vehroute.xml", "vehicle"),
        "disruption_events_equal": json.loads(
            (diagnostic_run_dir / "disruption-events.json").read_text(encoding="utf-8")
        )
        == json.loads(
            (original_run_dir / "disruption-events.json").read_text(encoding="utf-8")
        ),
        "aggregate_scientific_projection_equal": aggregate_projection_equal,
    }
    return {
        "diagnostic_raw_recomputation": diagnostic_raw,
        "original_raw_recomputation": original_raw,
        **checks,
        "pass": all(checks.values()),
    }


def normalized_exposure_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("run_id", None)
    return payload


def compare_diagnostic_pair(first_dir: Path, repeat_dir: Path) -> dict[str, Any]:
    base_metrics_first = json.loads((first_dir / "final-metrics.json").read_text())
    base_metrics_repeat = json.loads((repeat_dir / "final-metrics.json").read_text())
    checks = {
        "normalized_metrics_equal": BASE.scientific_metrics_projection(base_metrics_first)
        == BASE.scientific_metrics_projection(base_metrics_repeat),
        "step_trace_byte_equal": (first_dir / "step-trace.csv").read_bytes()
        == (repeat_dir / "step-trace.csv").read_bytes(),
        "vehicle_ledger_equal": json.loads(
            (first_dir / "vehicle-ledger.json").read_text()
        )
        == json.loads((repeat_dir / "vehicle-ledger.json").read_text()),
        "disruption_events_equal": json.loads(
            (first_dir / "disruption-events.json").read_text()
        )
        == json.loads((repeat_dir / "disruption-events.json").read_text()),
        "normalized_exposure_events_equal": normalized_exposure_payload(
            first_dir / "exposure-events.json"
        )
        == normalized_exposure_payload(repeat_dir / "exposure-events.json"),
        "normalized_exposure_summaries_equal": normalized_exposure_payload(
            first_dir / "exposure-summary.json"
        )
        == normalized_exposure_payload(repeat_dir / "exposure-summary.json"),
        "pre_event_occupancy_equal": json.loads(
            (first_dir / "pre-event-occupancy.json").read_text()
        )
        == json.loads((repeat_dir / "pre-event-occupancy.json").read_text()),
        "tripinfo_semantically_equal": canonical_xml_children(
            first_dir / "tripinfo.xml", "tripinfo"
        )
        == canonical_xml_children(repeat_dir / "tripinfo.xml", "tripinfo"),
        "vehroute_semantically_equal": canonical_xml_children(
            first_dir / "vehroute.xml", "vehicle"
        )
        == canonical_xml_children(repeat_dir / "vehroute.xml", "vehicle"),
    }
    return {**checks, "pass": all(checks.values())}


def visit_entry_period(
    visit: Mapping[str, Any], event_start: float, event_end: float
) -> str:
    start = float(visit["entry_transition_interval_start_seconds"])
    end = float(visit["entry_transition_interval_end_seconds"])
    if end <= event_start:
        return "BEFORE"
    if start >= event_end:
        return "AFTER"
    return "DURING"


def select_event_period_visit_pair(
    n0_visits: list[dict[str, Any]],
    d0_visits: list[dict[str, Any]],
    *,
    event_start: float,
    event_end: float,
    monitored_edge: str,
) -> dict[str, Any]:
    n0_edge_visits = [
        visit for visit in n0_visits if visit.get("edge_id") == monitored_edge
    ]
    d0_edge_visits = [
        visit for visit in d0_visits if visit.get("edge_id") == monitored_edge
    ]
    d0_candidates = [
        visit
        for visit in d0_edge_visits
        if visit_entry_period(visit, event_start, event_end) == "DURING"
    ]
    if len(d0_candidates) != 1:
        return {
            "status": "NOT_IDENTIFIABLE",
            "reason": "D0_EVENT_PERIOD_VISIT_NOT_UNIQUE",
            "d0_event_period_visit_count": len(d0_candidates),
        }
    d0_visit = d0_candidates[0]
    route_index = d0_visit.get("entry_route_index")
    if len(n0_edge_visits) == 1:
        n0_route_index = n0_edge_visits[0].get("entry_route_index")
        if (
            route_index is not None
            and n0_route_index is not None
            and route_index != n0_route_index
        ):
            return {
                "status": "NOT_IDENTIFIABLE",
                "reason": "ROUTE_INDEX_CONFLICT",
                "n0_entry_route_index": n0_route_index,
                "d0_entry_route_index": route_index,
            }
        return {
            "status": "IDENTIFIED",
            "pairing_basis": "UNIQUE_N0_TRAVERSAL",
            "n0_visit": n0_edge_visits[0],
            "d0_visit": d0_visit,
        }

    if route_index is not None:
        route_matches = [
            visit
            for visit in n0_edge_visits
            if visit.get("entry_route_index") == route_index
        ]
        if len(route_matches) == 1:
            return {
                "status": "IDENTIFIED",
                "pairing_basis": "UNIQUE_ROUTE_INDEX",
                "n0_visit": route_matches[0],
                "d0_visit": d0_visit,
            }

    occurrence = d0_visit.get("occurrence_index")
    occurrence_matches = [
        visit
        for visit in n0_edge_visits
        if visit.get("occurrence_index") == occurrence
        and (
            route_index is None
            or visit.get("entry_route_index") is None
            or visit.get("entry_route_index") == route_index
        )
    ]
    if (
        occurrence is not None
        and len(n0_edge_visits) == len(d0_edge_visits)
        and len(occurrence_matches) == 1
    ):
        return {
            "status": "IDENTIFIED",
            "pairing_basis": "MATCHED_TRAVERSAL_OCCURRENCE",
            "n0_visit": occurrence_matches[0],
            "d0_visit": d0_visit,
        }
    return {
        "status": "NOT_IDENTIFIABLE",
        "reason": "N0_CORRESPONDING_TRAVERSAL_NOT_UNIQUE",
        "n0_visit_count": len(n0_edge_visits),
        "d0_visit_count": len(d0_edge_visits),
        "d0_event_occurrence": occurrence,
        "d0_entry_route_index": route_index,
    }


def lane_sequence_for_edge_visit(
    summary: Mapping[str, Any], vehicle_id: str, edge_visit: Mapping[str, Any]
) -> list[str]:
    occurrence = edge_visit["occurrence_index"]
    edge_id = edge_visit["edge_id"]
    return [
        str(visit["lane_id"])
        for visit in summary["per_vehicle"][vehicle_id]["lane_visits"]
        if visit["edge_id"] == edge_id
        and visit["edge_visit_occurrence"] == occurrence
    ]


def paired_exposure_diagnostics(
    n0_dir: Path,
    d0_dir: Path,
    demand: dict[str, Any],
) -> dict[str, Any]:
    n0_summary = json.loads((n0_dir / "exposure-summary.json").read_text())
    d0_summary = json.loads((d0_dir / "exposure-summary.json").read_text())
    n0_tripinfo = parse_tripinfo_records(n0_dir / "tripinfo.xml")
    d0_tripinfo = parse_tripinfo_records(d0_dir / "tripinfo.xml")
    n0_ledger = json.loads((n0_dir / "vehicle-ledger.json").read_text())
    d0_ledger = json.loads((d0_dir / "vehicle-ledger.json").read_text())
    scheduled_departures = {
        str(item["vehicle_id"]): float(item["scheduled_departure_seconds"])
        for item in demand["scheduled_trips"]
    }
    exposed_ids = d0_summary["unique_edge_entries"]["during"]
    structural_ids = {
        str(item["vehicle_id"])
        for item in demand["scheduled_trips"]
        if MONITORED_EDGE in item["edges"]
    }
    frozen_route_count_exceptions = {
        str(item["vehicle_id"]): list(item["edges"]).count(MONITORED_EDGE)
        for item in demand["scheduled_trips"]
        if MONITORED_EDGE in item["edges"]
        and list(item["edges"]).count(MONITORED_EDGE) != 1
    }
    observed_traversal_count_exceptions = {
        vehicle_id: {
            "n0_visit_count": sum(
                visit["edge_id"] == MONITORED_EDGE
                for visit in n0_summary["per_vehicle"][vehicle_id]["edge_visits"]
            ),
            "d0_visit_count": sum(
                visit["edge_id"] == MONITORED_EDGE
                for visit in d0_summary["per_vehicle"][vehicle_id]["edge_visits"]
            ),
        }
        for vehicle_id in sorted(structural_ids)
        if sum(
            visit["edge_id"] == MONITORED_EDGE
            for visit in n0_summary["per_vehicle"][vehicle_id]["edge_visits"]
        )
        != 1
        or sum(
            visit["edge_id"] == MONITORED_EDGE
            for visit in d0_summary["per_vehicle"][vehicle_id]["edge_visits"]
        )
        != 1
    }
    comparisons: list[dict[str, Any]] = []
    complete = True
    for vehicle_id in exposed_ids:
        n0_visits = n0_summary["per_vehicle"][vehicle_id]["edge_visits"]
        d0_visits = d0_summary["per_vehicle"][vehicle_id]["edge_visits"]
        selected = select_event_period_visit_pair(
            n0_visits,
            d0_visits,
            event_start=DISRUPTION_START,
            event_end=DISRUPTION_END,
            monitored_edge=MONITORED_EDGE,
        )
        if selected["status"] != "IDENTIFIED":
            complete = False
            comparisons.append(
                {
                    "vehicle_id": vehicle_id,
                    "status": "NOT_IDENTIFIABLE",
                    "scheduled_departure_seconds": scheduled_departures[vehicle_id],
                    "selection": selected,
                }
            )
            continue
        n0_visit = selected["n0_visit"]
        d0_visit = selected["d0_visit"]
        n0_lanes = lane_sequence_for_edge_visit(n0_summary, vehicle_id, n0_visit)
        d0_lanes = lane_sequence_for_edge_visit(d0_summary, vehicle_id, d0_visit)
        n0_values = {
            "edge_entry_observed_at_seconds": n0_visit["entry_observed_at_seconds"],
            "edge_entry_interval_seconds": [
                n0_visit["entry_transition_interval_start_seconds"],
                n0_visit["entry_transition_interval_end_seconds"],
            ],
            "edge_exit_observed_at_seconds": n0_visit["exit_observed_at_seconds"],
            "edge_exit_interval_seconds": [
                n0_visit["exit_transition_interval_start_seconds"],
                n0_visit["exit_transition_interval_end_seconds"],
            ],
            "observed_edge_time_seconds": n0_visit["observed_edge_time_seconds"],
            "lane_sequence": n0_lanes,
            "observed_edge_halting_seconds": n0_visit[
                "observed_halting_seconds"
            ],
            "final_arrival_seconds": n0_tripinfo[vehicle_id]["arrival_seconds"],
            "restricted_trip_time_seconds": n0_ledger[vehicle_id][
                "restricted_trip_time_seconds"
            ],
            "native_waiting_time_seconds": n0_tripinfo[vehicle_id][
                "waiting_time_seconds"
            ],
        }
        d0_values = {
            "edge_entry_observed_at_seconds": d0_visit["entry_observed_at_seconds"],
            "edge_entry_interval_seconds": [
                d0_visit["entry_transition_interval_start_seconds"],
                d0_visit["entry_transition_interval_end_seconds"],
            ],
            "edge_exit_observed_at_seconds": d0_visit["exit_observed_at_seconds"],
            "edge_exit_interval_seconds": [
                d0_visit["exit_transition_interval_start_seconds"],
                d0_visit["exit_transition_interval_end_seconds"],
            ],
            "observed_edge_time_seconds": d0_visit["observed_edge_time_seconds"],
            "lane_sequence": d0_lanes,
            "observed_edge_halting_seconds": d0_visit[
                "observed_halting_seconds"
            ],
            "final_arrival_seconds": d0_tripinfo[vehicle_id]["arrival_seconds"],
            "restricted_trip_time_seconds": d0_ledger[vehicle_id][
                "restricted_trip_time_seconds"
            ],
            "native_waiting_time_seconds": d0_tripinfo[vehicle_id][
                "waiting_time_seconds"
            ],
        }
        deltas = {
            key: float(d0_values[key]) - float(n0_values[key])
            for key in (
                "edge_entry_observed_at_seconds",
                "edge_exit_observed_at_seconds",
                "observed_edge_time_seconds",
                "observed_edge_halting_seconds",
                "final_arrival_seconds",
                "restricted_trip_time_seconds",
                "native_waiting_time_seconds",
            )
        }
        comparisons.append(
            {
                "vehicle_id": vehicle_id,
                "status": "IDENTIFIED",
                "pairing_basis": selected["pairing_basis"],
                "scheduled_departure_seconds": scheduled_departures[vehicle_id],
                "n0": n0_values,
                "d0": d0_values,
                "d0_minus_n0": deltas,
                "lane_choice_difference_observed": n0_lanes != d0_lanes,
                "n0_lane_change_count": max(0, len(n0_lanes) - 1),
                "d0_lane_change_count": max(0, len(d0_lanes) - 1),
            }
        )

    lane_choice_observed = any(
        item["lane_choice_difference_observed"]
        for item in comparisons
        if item["status"] == "IDENTIFIED"
    )
    additional_wait_observed = any(
        item["d0_minus_n0"]["observed_edge_halting_seconds"] > 0
        for item in comparisons
        if item["status"] == "IDENTIFIED"
    )
    lane_change_observed = any(
        item["d0_lane_change_count"] != item["n0_lane_change_count"]
        for item in comparisons
        if item["status"] == "IDENTIFIED"
    )
    delayed_entry_observed = any(
        item["d0_minus_n0"]["edge_entry_observed_at_seconds"] > 0
        for item in comparisons
        if item["status"] == "IDENTIFIED"
    )
    delayed_exit_observed = any(
        item["d0_minus_n0"]["edge_exit_observed_at_seconds"] > 0
        for item in comparisons
        if item["status"] == "IDENTIFIED"
    )
    category = lambda observed: (
        "NOT_IDENTIFIABLE"
        if not complete or not exposed_ids
        else "OBSERVED"
        if observed
        else "NOT_OBSERVED"
    )
    return {
        "status": "PASS" if complete else "INCONCLUSIVE",
        "comparison_cohort": "D0 vehicles observed entering A1B1 during [300,600)",
        "vehicle_count": len(exposed_ids),
        "vehicle_ids": exposed_ids,
        "frozen_structurally_exposed_vehicle_count": len(structural_ids),
        "frozen_structurally_exposed_vehicles_traverse_A1B1_exactly_once": not frozen_route_count_exceptions,
        "frozen_structural_route_count_exceptions": frozen_route_count_exceptions,
        "observed_structural_vehicles_traverse_A1B1_once_per_condition": not observed_traversal_count_exceptions,
        "observed_traversal_count_exceptions": observed_traversal_count_exceptions,
        "comparisons": comparisons,
        "mechanism_characterization": {
            "lane_choice_difference": category(lane_choice_observed),
            "additional_wait_on_A1B1": category(additional_wait_observed),
            "lane_change_on_A1B1": category(lane_change_observed),
            "delayed_edge_entry": category(delayed_entry_observed),
            "delayed_edge_exit": category(delayed_exit_observed),
        },
        "causal_claim_made": False,
        "timestamp_precision": "ONE_SECOND_OBSERVATION_INTERVALS",
    }


def event_at(events: Iterable[Mapping[str, Any]], name: str, timestamp: float) -> bool:
    return any(
        item["event"] == name
        and math.isclose(float(item["observed_at_seconds"]), timestamp, abs_tol=1e-12)
        for item in events
    )


def restricted_lane_compliance(
    exposure_summary: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
    *,
    restricted_lane: str,
    activation_time: float,
    restoration_time: float,
) -> dict[str, Any]:
    """Evaluate compliance from lane visits, never from unique-user subtraction."""

    lane_diagnostics = exposure_summary["lane_visit_diagnostics"][restricted_lane]
    event_list = list(events)
    activation_events = [
        item
        for item in event_list
        if item["event"] == "RESTRICTION_ACTIVATION"
        and item.get("lane_id") == restricted_lane
        and math.isclose(
            float(item["observed_at_seconds"]), activation_time, abs_tol=1e-12
        )
    ]
    restoration_events = [
        item
        for item in event_list
        if item["event"] == "RESTORATION"
        and item.get("lane_id") == restricted_lane
        and math.isclose(
            float(item["observed_at_seconds"]), restoration_time, abs_tol=1e-12
        )
    ]
    lifecycle_observed = len(activation_events) == 1 and len(restoration_events) == 1
    observability_complete = bool(
        exposure_summary.get("exposure_observability_complete")
    )
    post_activation_entry_count = int(
        lane_diagnostics["post_activation_entry_count"]
    )
    compliant = (
        observability_complete
        and lifecycle_observed
        and post_activation_entry_count == 0
    )
    return {
        "status": "PASS" if compliant else "FAIL",
        "observability_complete": observability_complete,
        "activation_observed_exactly_once": len(activation_events) == 1,
        "restoration_observed_exactly_once": len(restoration_events) == 1,
        "lifecycle_observed": lifecycle_observed,
        "preexisting_occupant_ids": lane_diagnostics["preexisting_occupant_ids"],
        "preexisting_occupant_count": lane_diagnostics[
            "preexisting_occupant_count"
        ],
        "post_activation_entry_ids": lane_diagnostics[
            "post_activation_entry_ids"
        ],
        "post_activation_entry_count": post_activation_entry_count,
        "compliance_basis": "POST_ACTIVATION_RESTRICTED_LANE_ENTRY_COUNT_EQUALS_ZERO",
    }


def determine_diagnostic_status(
    *,
    scientific_noninterference: bool,
    determinism_pass: bool,
    static_noninterference_pass: bool,
    original_evidence_unchanged: bool,
    lifecycle_observed: bool,
    compliance_observed: bool,
    exposure_observability_complete: bool,
    paired_diagnostics_status: str,
) -> str:
    """Return integrity status without treating a zero exposure count as failure."""

    integrity_failure = (
        not scientific_noninterference
        or not determinism_pass
        or not static_noninterference_pass
        or not original_evidence_unchanged
        or not lifecycle_observed
        or not compliance_observed
    )
    if integrity_failure:
        return "FAIL"
    if not exposure_observability_complete or paired_diagnostics_status != "PASS":
        return "INCONCLUSIVE"
    return "PASS"


def finalize_inventory(summary: dict[str, Any]) -> None:
    summary_path = ATTEMPT_CHECKS / "bundle-summary.json"
    inventory_path = ATTEMPT_CHECKS / "evidence-inventory.json"
    hash_path = ATTEMPT_CHECKS / "artifact-sha256.json"
    write_json_once(summary_path, summary)
    existing = sorted(
        path.as_posix()
        for path in Path(".").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path not in {inventory_path, hash_path}
    )
    artifacts = sorted(set(existing) | {inventory_path.as_posix(), hash_path.as_posix()})
    write_json_once(
        inventory_path,
        {
            "bundle_root_identity": EVIDENCE_IDENTITY,
            "artifact_count_total_including_hash_manifest": len(artifacts),
            "artifact_count_excluding_hash_manifest": len(artifacts) - 1,
            "artifacts": artifacts,
            "hash_manifest_self_hash_included": False,
        },
    )
    paths_to_hash = sorted(
        path
        for path in Path(".").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path != hash_path
    )
    hashes = {path.as_posix(): sha256(path) for path in paths_to_hash}
    write_json_once(
        hash_path,
        {"sha256": dict(sorted(hashes.items())), "self_hash_included": False},
    )
    if any(sha256(Path(identity)) != expected for identity, expected in hashes.items()):
        raise AssertionError("diagnostic artifact hash verification failed")


def environment_receipt() -> dict[str, Any]:
    sumo_result = subprocess.run(
        ["sumo", "--version"], check=True, capture_output=True, text=True
    )
    first_line = (sumo_result.stdout or sumo_result.stderr).splitlines()[0]
    return {
        "python_version": sys.version.split()[0],
        "sumo_version_line": first_line,
        "diagnostic_identity": DIAGNOSTIC_IDENTITY,
        "simulation_executed_by_version_check": False,
    }


def main() -> None:
    global ATTEMPT_INITIALIZED
    if Path.cwd().resolve() != BUNDLE_ROOT:
        raise AssertionError("diagnostic runner must be launched from its bundle root")
    if DIAGNOSTIC_IDENTITY != OBSERVER_IDENTITY:
        raise AssertionError("runner and observer diagnostic identities differ")
    configure_base_runner()
    BASE.verify_pristine_targets()
    ATTEMPT_CHECKS.mkdir(parents=True)
    ATTEMPT_INITIALIZED = True

    original_before = tree_snapshot(ORIGINAL_ROOT)
    write_json_once(
        ATTEMPT_CHECKS / "original-b0-state-before.json",
        {
            "object_count": len(original_before),
            "tree_digest": snapshot_digest(original_before),
        },
    )
    runner_hash = sha256(RUNNER_PATH)
    observer_hash = sha256(OBSERVER_PATH)
    write_bytes_once(
        ATTEMPT_CHECKS / "run_b0_exposure_diagnostic.executed.py",
        RUNNER_PATH.read_bytes(),
    )
    write_bytes_once(
        ATTEMPT_CHECKS / "exposure_observer.executed.py", OBSERVER_PATH.read_bytes()
    )
    write_json_once(
        ATTEMPT_CHECKS / "runner-and-observer-sha256.json",
        {
            "runner_sha256": runner_hash,
            "observer_sha256": observer_hash,
            "original_b0_runner_sha256": EXPECTED_ORIGINAL_RUNNER_SHA256,
            "run_attempt": RUN_ATTEMPT,
        },
    )
    input_receipt = verify_frozen_inputs()
    write_json_once(ATTEMPT_CHECKS / "frozen-input-reconciliation.json", input_receipt)
    noninterference_contract = verify_observer_noninterference_contract()
    write_json_once(
        ATTEMPT_CHECKS / "observer-noninterference-contract.json",
        noninterference_contract,
    )
    test_receipt = run_preflight_tests()
    write_json_once(ATTEMPT_CHECKS / "pre-execution-tests.json", test_receipt)
    write_json_once(ATTEMPT_CHECKS / "environment.json", environment_receipt())

    repository_before = BASE.repository_state()
    write_json_once(ATTEMPT_CHECKS / "repository-state-before.json", repository_before)

    demand = json.loads(Path("inputs/demand-manifest.json").read_text(encoding="utf-8"))
    input_hashes = input_receipt["sha256"]
    structural_ids = {
        str(item["vehicle_id"])
        for item in demand["scheduled_trips"]
        if MONITORED_EDGE in item["edges"]
    }
    if len(structural_ids) != 15:
        raise AssertionError("unexpected frozen structural-exposure cohort")

    metrics_by_id: dict[str, dict[str, Any]] = {}
    for run_id, _, output_identity, disrupted in RUN_PLAN:
        metrics_by_id[run_id] = run_observed_condition(
            run_id=run_id,
            output_identity=output_identity,
            disrupted=disrupted,
            input_hashes=input_hashes,
            demand=demand,
            runner_hash=runner_hash,
            observer_hash=observer_hash,
            structural_ids=structural_ids,
        )

    repository_after = BASE.repository_state()
    if repository_after != repository_before:
        raise AssertionError("public repository state changed during diagnostic execution")
    write_json_once(ATTEMPT_CHECKS / "repository-state-after.json", repository_after)

    original_after = tree_snapshot(ORIGINAL_ROOT)
    original_unchanged = original_before == original_after
    write_json_once(
        ATTEMPT_CHECKS / "original-b0-immutability.json",
        {
            "status": "PASS" if original_unchanged else "FAIL",
            "object_count_before": len(original_before),
            "object_count_after": len(original_after),
            "tree_digest_before": snapshot_digest(original_before),
            "tree_digest_after": snapshot_digest(original_after),
        },
    )
    if not original_unchanged:
        raise AssertionError("original B0 bundle changed during diagnostic execution")

    comparison_by_run: dict[str, Any] = {}
    for run_id, original_id, output_identity, _ in RUN_PLAN:
        original_dir = (
            ORIGINAL_ROOT
            / "runs"
            / original_id.lower()
            / "attempt-002"
        )
        comparison_by_run[run_id] = compare_scientific_run(
            Path(output_identity), original_dir, metrics_by_id[run_id], demand
        )
    scientific_noninterference = all(
        item["pass"] for item in comparison_by_run.values()
    )
    write_json_once(
        ATTEMPT_CHECKS / "original-metric-reconciliation.json",
        {
            "status": "PASS" if scientific_noninterference else "FAIL",
            "comparisons": comparison_by_run,
        },
    )

    determinism = {
        "normal": compare_diagnostic_pair(
            Path(RUN_PLAN[0][2]), Path(RUN_PLAN[2][2])
        ),
        "disrupted": compare_diagnostic_pair(
            Path(RUN_PLAN[1][2]), Path(RUN_PLAN[3][2])
        ),
    }
    determinism["pass"] = determinism["normal"]["pass"] and determinism[
        "disrupted"
    ]["pass"]
    write_json_once(
        ATTEMPT_CHECKS / "normalized-determinism-comparison.json", determinism
    )

    paired = paired_exposure_diagnostics(
        Path(RUN_PLAN[0][2]), Path(RUN_PLAN[1][2]), demand
    )
    write_json_once(
        ATTEMPT_CHECKS / "exposed-vehicle-paired-diagnostics.json", paired
    )

    d0_dir = Path(RUN_PLAN[1][2])
    d0_exposure = json.loads((d0_dir / "exposure-summary.json").read_text())
    d0_events = json.loads((d0_dir / "exposure-events.json").read_text())["events"]
    d0_occupancy = json.loads((d0_dir / "pre-event-occupancy.json").read_text())
    lane0_count = d0_exposure["unique_event_lane_user_counts"][RESTRICTED_LANE]
    lane1_count = d0_exposure["unique_event_lane_user_counts"][SURVIVING_LANE]
    restricted_lane_diagnostics = d0_exposure["lane_visit_diagnostics"][
        RESTRICTED_LANE
    ]
    surviving_lane_diagnostics = d0_exposure["lane_visit_diagnostics"][
        SURVIVING_LANE
    ]
    exposure_count = d0_exposure["unique_edge_entry_counts"]["during"]
    exposure_observability_complete = bool(
        d0_exposure["exposure_observability_complete"]
    )
    compliance = restricted_lane_compliance(
        d0_exposure,
        d0_events,
        restricted_lane=RESTRICTED_LANE,
        activation_time=DISRUPTION_START,
        restoration_time=DISRUPTION_END,
    )
    lifecycle_observed = bool(compliance["lifecycle_observed"])
    compliance_observed = compliance["status"] == "PASS"
    direct_event_validated = (
        compliance_observed
        and exposure_observability_complete
        and metrics_by_id["D0-DIAG"]["disruption_application_validated"] is True
        and metrics_by_id["D0-DIAG"]["permission_restoration_confirmed"] is True
    )
    empirical_substrate_validated = (
        direct_event_validated
        and scientific_noninterference
        and determinism["pass"]
        and paired["status"] == "PASS"
        and noninterference_contract["status"] == "PASS"
        and original_unchanged
    )
    diagnostic_status = determine_diagnostic_status(
        scientific_noninterference=scientific_noninterference,
        determinism_pass=bool(determinism["pass"]),
        static_noninterference_pass=noninterference_contract["status"] == "PASS",
        original_evidence_unchanged=original_unchanged,
        lifecycle_observed=lifecycle_observed,
        compliance_observed=compliance_observed,
        exposure_observability_complete=exposure_observability_complete,
        paired_diagnostics_status=str(paired["status"]),
    )
    if diagnostic_status == "PASS":
        next_task = (
            "BASELINE_ONLY_CALIBRATE_AND_FREEZE_A_SCIENTIFICALLY_INFORMATIVE_"
            "DISRUPTION_SCENARIO_BEFORE_ANY_RL_OR_TREATMENT"
        )
    elif diagnostic_status == "INCONCLUSIVE":
        next_task = (
            "BASELINE_ONLY_RESOLVE_THE_REMAINING_PER_VEHICLE_EXPOSURE_"
            "OBSERVABILITY_GAP_WITHOUT_CHANGING_THE_FROZEN_SCENARIO"
        )
    else:
        next_task = (
            "REPAIR_THE_B0_EXPOSURE_DIAGNOSTIC_INTEGRITY_DEFECT_WITHOUT_"
            "CHANGING_SCIENTIFIC_INPUTS_BEFORE_A_NEW_ATTEMPT"
        )
    summary = {
        "diagnostic_identity": DIAGNOSTIC_IDENTITY,
        "diagnostic_status": diagnostic_status,
        "run_attempt": RUN_ATTEMPT,
        "run_order": [item[0] for item in RUN_PLAN],
        "frozen_b0_scientific_inputs_unchanged": True,
        "diagnostic_evidence_isolated": True,
        "per_vehicle_exposure_observer_implemented": True,
        "observer_noninterference_contract": noninterference_contract["status"],
        "d0_pre_activation_lane0_occupancy": d0_occupancy["lane_occupancy"][
            RESTRICTED_LANE
        ],
        "d0_pre_activation_lane1_occupancy": d0_occupancy["lane_occupancy"][
            SURVIVING_LANE
        ],
        "d0_unique_vehicles_entering_edge_during_event": exposure_count,
        "exposure_observability_complete": exposure_observability_complete,
        "positive_event_traffic_exposure_observed": exposure_count > 0,
        "d0_unique_passenger_vehicles_using_lane0_during_event": lane0_count,
        "d0_unique_passenger_vehicles_using_lane1_during_event": lane1_count,
        "d0_restricted_lane_preexisting_occupant_ids": restricted_lane_diagnostics[
            "preexisting_occupant_ids"
        ],
        "d0_restricted_lane_preexisting_occupant_count": restricted_lane_diagnostics[
            "preexisting_occupant_count"
        ],
        "d0_restricted_lane_post_activation_entry_ids": restricted_lane_diagnostics[
            "post_activation_entry_ids"
        ],
        "d0_restricted_lane_post_activation_entry_count": restricted_lane_diagnostics[
            "post_activation_entry_count"
        ],
        "d0_surviving_lane_event_entry_count": surviving_lane_diagnostics[
            "post_activation_entry_count"
        ],
        "d0_surviving_lane_event_unique_use_count": surviving_lane_diagnostics[
            "event_unique_user_count"
        ],
        "d0_exposed_vehicle_ids": d0_exposure["unique_edge_entries"]["during"],
        "restricted_lane_compliance": compliance,
        "disruption_traffic_compliance_directly_observed": compliance_observed,
        "actual_disruption_traffic_exposure_confirmed": exposure_count > 0,
        "exposed_vehicle_paired_diagnostics_complete": paired["status"] == "PASS",
        "diagnostic_observer_scientific_noninterference": (
            "PASS" if scientific_noninterference else "FAIL"
        ),
        "exposure_diagnostic_determinism": (
            "PASS" if determinism["pass"] else "FAIL"
        ),
        "b0_disruption_event_directly_validated": direct_event_validated,
        "b0_empirical_substrate_now_validated": empirical_substrate_validated,
        "b0_current_disruption_scenario_suitability": "TOO_WEAK",
        "exposure_observer_reusable_for_future_baselines": True,
        "public_git_modified": False,
        "original_b0_bundle_modified": False,
        "next_task": next_task,
    }
    finalize_inventory(summary)


def seal_failed_attempt(error: BaseException) -> None:
    if not ATTEMPT_INITIALIZED:
        return
    failure_path = ATTEMPT_CHECKS / "bundle-failure.json"
    if not failure_path.exists():
        write_json_once(
            failure_path,
            {
                "status": "INCOMPLETE_ATTEMPT",
                "diagnostic_identity": DIAGNOSTIC_IDENTITY,
                "run_attempt": RUN_ATTEMPT,
                "exception_type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
                "wall_clock_detected_utc": utc_now(),
                "scientific_inputs_may_not_be_changed_for_retry": True,
            },
        )
    repository_path = ATTEMPT_CHECKS / "repository-state-after-failure.json"
    if not repository_path.exists():
        try:
            state: dict[str, Any] = {
                "read_succeeded": True,
                "state": BASE.read_repository_state(),
            }
        except Exception as repository_error:
            state = {"read_succeeded": False, "error": str(repository_error)}
        write_json_once(repository_path, state)
    original_after_failure = tree_snapshot(ORIGINAL_ROOT)
    original_before_path = ATTEMPT_CHECKS / "original-b0-state-before.json"
    original_failure_path = (
        ATTEMPT_CHECKS / "original-b0-immutability-after-failure.json"
    )
    if not original_failure_path.exists():
        before_record = (
            json.loads(original_before_path.read_text(encoding="utf-8"))
            if original_before_path.exists()
            else None
        )
        after_digest = snapshot_digest(original_after_failure)
        write_json_once(
            original_failure_path,
            {
                "comparison_available": before_record is not None,
                "status": (
                    "PASS"
                    if before_record is not None
                    and before_record["object_count"] == len(original_after_failure)
                    and before_record["tree_digest"] == after_digest
                    else "NOT_ESTABLISHED"
                ),
                "object_count_after_failure": len(original_after_failure),
                "tree_digest_after_failure": after_digest,
            },
        )
    inventory_path = ATTEMPT_CHECKS / "failure-evidence-inventory.json"
    hash_path = ATTEMPT_CHECKS / "failure-artifact-sha256.json"
    if not inventory_path.exists() and not hash_path.exists():
        artifacts: set[Path] = set()
        for _, _, output_identity, _ in RUN_PLAN:
            run_root = Path(output_identity)
            if run_root.exists():
                artifacts.update(
                    path
                    for path in run_root.rglob("*")
                    if path.is_file() and "__pycache__" not in path.parts
                )
        artifacts.update(
            path
            for path in ATTEMPT_CHECKS.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path not in {inventory_path, hash_path}
        )
        artifacts = set(sorted(artifacts))
        identities = sorted(
            {path.as_posix() for path in artifacts}
            | {inventory_path.as_posix(), hash_path.as_posix()}
        )
        write_json_once(
            inventory_path,
            {
                "bundle_root_identity": EVIDENCE_IDENTITY,
                "run_attempt": RUN_ATTEMPT,
                "attempt_status": "INCOMPLETE_ATTEMPT",
                "artifacts": identities,
                "hash_manifest_self_hash_included": False,
            },
        )
        files_to_hash = sorted(
            path
            for path in artifacts | {inventory_path}
            if path != hash_path
        )
        write_json_once(
            hash_path,
            {
                "sha256": {
                    path.as_posix(): sha256(path) for path in files_to_hash
                },
                "self_hash_included": False,
            },
        )


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        seal_failed_attempt(error)
        raise
