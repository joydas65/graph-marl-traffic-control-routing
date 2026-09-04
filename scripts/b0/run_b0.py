#!/usr/bin/env python3
"""Run the frozen local-only B0 fixed-time baseline bundle exactly once."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import subprocess
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import traci


SEED = 20260904
H_PILOT = 1500
STEP_SECONDS = 1.0
RUN_ATTEMPT = 2
DISRUPTION_START = 300
DISRUPTION_END = 600
DISRUPTED_EDGE_ID = "A1B1"
DISRUPTED_LANE_ID = "A1B1_0"
REMAINING_LANE_ID = "A1B1_1"
PASSENGER_CLASS = "passenger"
INPUT_HASHES = Path("checks/input-sha256.json")
DEMAND_MANIFEST = Path("inputs/demand-manifest.json")
SCENARIO_MANIFEST = Path("inputs/scenario-manifest.json")
DISRUPTION_MANIFEST = Path("inputs/disruption-specification.json")
RUNNER_PATH = Path("run_b0.py")
EXPECTED_REPOSITORY_SHA = "2a0da664c8f43a1e346c3c405fbff3fc40a78778"
BUNDLE_ROOT = Path(__file__).resolve().parent

RUN_PLAN = (
    ("N0", f"runs/n0/attempt-{RUN_ATTEMPT:03d}", False),
    ("D0", f"runs/d0/attempt-{RUN_ATTEMPT:03d}", True),
    ("N0-R", f"runs/n0-r/attempt-{RUN_ATTEMPT:03d}", False),
    ("D0-R", f"runs/d0-r/attempt-{RUN_ATTEMPT:03d}", True),
)
ATTEMPT_CHECKS = Path("checks") / f"attempt-{RUN_ATTEMPT:03d}"
ATTEMPT_INITIALIZED = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary_path = path.with_name(f".{path.name}.tmp")
    with temporary_path.open("x", encoding="utf-8") as handle:
        handle.write(json_text(value))
        handle.flush()
        os.fsync(handle.fileno())
    temporary_path.replace(path)


def json_text(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def write_json_once(path: Path, value: object) -> None:
    if path.exists():
        raise AssertionError(f"refusing to overwrite {path.as_posix()}")
    write_json(path, value)


def write_bytes_once(path: Path, value: bytes) -> None:
    if path.exists():
        raise AssertionError(f"refusing to overwrite {path.as_posix()}")
    temporary_path = path.with_name(f".{path.name}.tmp")
    with temporary_path.open("xb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    temporary_path.replace(path)


def verify_frozen_inputs() -> dict[str, str]:
    recorded = json.loads(INPUT_HASHES.read_text(encoding="utf-8"))["sha256"]
    mismatches = {
        identity: {"expected": expected, "actual": sha256(Path(identity))}
        for identity, expected in recorded.items()
        if sha256(Path(identity)) != expected
    }
    if mismatches:
        raise AssertionError(f"frozen input hash mismatch: {mismatches}")
    return dict(sorted(recorded.items()))


def git_output(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=BUNDLE_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def read_repository_state() -> dict[str, Any]:
    repository_root = Path(git_output("rev-parse", "--show-toplevel")).resolve()
    relative_bundle = BUNDLE_ROOT.relative_to(repository_root).as_posix()
    ignore_check = subprocess.run(
        ["git", "check-ignore", "-q", relative_bundle],
        cwd=repository_root,
        check=False,
    )
    porcelain = git_output("status", "--porcelain=v1", "--untracked-files=all")
    state = {
        "repository_sha": git_output("rev-parse", "HEAD"),
        "branch": git_output("branch", "--show-current"),
        "worktree_and_index_clean": not porcelain,
        "local_evidence_bundle_ignored": ignore_check.returncode == 0,
    }
    return state


def repository_state() -> dict[str, Any]:
    state = read_repository_state()
    if state != {
        "repository_sha": EXPECTED_REPOSITORY_SHA,
        "branch": "main",
        "worktree_and_index_clean": True,
        "local_evidence_bundle_ignored": True,
    }:
        raise AssertionError(f"unexpected public repository state: {state}")
    return state


def verify_frozen_contract(
    scenario: dict[str, Any],
    disruption: dict[str, Any],
    demand: dict[str, Any],
) -> dict[str, Any]:
    expected_scenario = {
        "repository_sha": EXPECTED_REPOSITORY_SHA,
        "scenario_seed": SEED,
        "routes_fixed_before_simulation": True,
        "fixed_time_signals": True,
        "traffic_light_control_via_traci": False,
        "dynamic_rerouting": False,
        "simulation_start_seconds": 0,
        "demand_end_seconds": 900,
        "clearance_window_seconds": 600,
        "h_pilot_seconds": H_PILOT,
        "simulation_step_seconds": STEP_SECONDS,
        "disruption_start_seconds": DISRUPTION_START,
        "disruption_end_seconds": DISRUPTION_END,
        "conditions_in_execution_order": [item[0] for item in RUN_PLAN],
        "capacity_conditioned_treatment_implemented": False,
        "capacity_conditioned_treatment_result_exists": False,
    }
    expected_disruption = {
        "condition": "D0",
        "disruption_family": "TEMPORARY_SINGLE_LINK_PARTIAL_CAPACITY_REDUCTION",
        "implementation": "TEMPORARY_ONE_LANE_LOSS_CAPACITY_PROXY",
        "directed_edge_id": DISRUPTED_EDGE_ID,
        "lane_id": DISRUPTED_LANE_ID,
        "remaining_route_feasible_lane_id": REMAINING_LANE_ID,
        "vehicle_class_temporarily_disallowed": PASSENGER_CLASS,
        "start_step_inclusive": DISRUPTION_START,
        "end_step_exclusive": DISRUPTION_END,
        "full_link_closure": False,
        "rerouting_permitted": False,
        "exact_capacity_percentage_claimed": False,
    }
    expected_demand = {
        "scenario_seed": SEED,
        "scheduled_trip_count": 180,
        "route_count": 12,
        "routes_fixed_before_simulation": True,
        "dynamic_rerouting": False,
        "demand_window_seconds": {"start_inclusive": 0, "end_exclusive": 900},
    }
    mismatches: dict[str, dict[str, Any]] = {}
    for section, actual, expected in (
        ("scenario", scenario, expected_scenario),
        ("disruption", disruption, expected_disruption),
        ("demand", demand, expected_demand),
    ):
        for key, expected_value in expected.items():
            actual_value = actual.get(key)
            if actual_value != expected_value:
                mismatches[f"{section}.{key}"] = {
                    "expected": expected_value,
                    "actual": actual_value,
                }
    if mismatches:
        raise AssertionError(f"runner/frozen-contract mismatch: {mismatches}")
    return {
        "status": "PASS",
        "run_attempt": RUN_ATTEMPT,
        "run_order": [item[0] for item in RUN_PLAN],
        "runner_constants_match_frozen_manifests": True,
    }


def verify_pristine_targets() -> None:
    targets = [Path(output_identity) for _, output_identity, _ in RUN_PLAN]
    targets.append(ATTEMPT_CHECKS)
    existing = sorted(path.as_posix() for path in targets if path.exists())
    if existing:
        raise AssertionError(f"refusing non-pristine B0 execution targets: {existing}")

    prior_attempts = sorted(
        int(path.name.removeprefix("attempt-"))
        for path in Path("checks").glob("attempt-[0-9][0-9][0-9]")
        if path.is_dir() and path.name.removeprefix("attempt-").isdigit()
    )
    expected_prior_attempts = list(range(1, RUN_ATTEMPT))
    if prior_attempts != expected_prior_attempts:
        raise AssertionError(
            "bundle attempts must be sequential and gap-free: "
            f"found={prior_attempts}, expected={expected_prior_attempts}"
        )
    for prior_attempt in prior_attempts:
        prior_root = Path("checks") / f"attempt-{prior_attempt:03d}"
        required_failure_seal = [
            prior_root / "bundle-failure.json",
            prior_root / "failure-evidence-inventory.json",
            prior_root / "failure-artifact-sha256.json",
        ]
        missing = [path.as_posix() for path in required_failure_seal if not path.exists()]
        if missing:
            raise AssertionError(
                f"prior bundle attempt {prior_attempt} is not a sealed failure: {missing}"
            )


def lane_permissions(connection: Any, lane_id: str) -> dict[str, list[str]]:
    return {
        "allowed": sorted(connection.lane.getAllowed(lane_id)),
        "disallowed": sorted(connection.lane.getDisallowed(lane_id)),
    }


def passenger_allowed(permissions: dict[str, list[str]]) -> bool:
    allowed = permissions["allowed"]
    disallowed = permissions["disallowed"]
    return (not allowed or PASSENGER_CLASS in allowed) and PASSENGER_CLASS not in disallowed


def build_sumo_command(run_dir: Path) -> list[str]:
    return [
        "sumo",
        "-c",
        "inputs/b0.sumocfg",
        "--seed",
        str(SEED),
        "--device.rerouting.probability",
        "0",
        "--person-device.rerouting.probability",
        "0",
        "--tripinfo-output",
        (run_dir / "tripinfo.xml").as_posix(),
        "--tripinfo-output.write-unfinished",
        "true",
        "--tripinfo-output.write-undeparted",
        "true",
        "--vehroute-output",
        (run_dir / "vehroute.xml").as_posix(),
        "--vehroute-output.write-unfinished",
        "true",
        "--vehroute-output.intended-depart",
        "true",
        "--vehroute-output.sorted",
        "true",
        "--summary-output",
        (run_dir / "summary.xml").as_posix(),
        "--collision-output",
        (run_dir / "collisions.xml").as_posix(),
        "--log",
        (run_dir / "simulator.log").as_posix(),
        "--error-log",
        (run_dir / "simulator-errors.log").as_posix(),
    ]


def parse_tripinfo(path: Path) -> dict[str, dict[str, float | None]]:
    records: dict[str, dict[str, float | None]] = {}
    for node in ET.parse(path).getroot().findall("tripinfo"):
        vehicle_id = node.attrib["id"]
        if vehicle_id in records:
            raise AssertionError(f"duplicate tripinfo record for {vehicle_id}")
        depart = float(node.attrib["depart"])
        arrival = float(node.attrib["arrival"])
        records[vehicle_id] = {
            "actual_departure_seconds": None if depart < 0 else depart,
            "arrival_seconds": None if arrival < 0 else arrival,
            "waiting_time_seconds": float(node.attrib["waitingTime"]),
            "time_loss_seconds": float(node.attrib["timeLoss"]),
            "duration_seconds": float(node.attrib["duration"]),
            "route_length_metres": float(node.attrib["routeLength"]),
        }
    return records


def count_collisions(path: Path) -> int:
    if not path.exists():
        return 0
    return len(ET.parse(path).getroot().findall("collision"))


def nearest_rank_p95(values: list[float]) -> float:
    ordered = sorted(values)
    rank = math.ceil(0.95 * len(ordered))
    return ordered[rank - 1]


def scientific_metrics_projection(metrics: dict[str, Any]) -> dict[str, Any]:
    excluded = {
        "run_id",
        "condition_label",
        "attempt",
        "wall_clock_started_utc",
        "wall_clock_finished_utc",
        "simulation_wall_clock_runtime_seconds",
        "output_identity",
    }
    return {key: value for key, value in metrics.items() if key not in excluded}


def run_condition(
    run_id: str,
    output_identity: str,
    disrupted: bool,
    input_hashes: dict[str, str],
    demand: dict[str, Any],
    frozen_runner_hash: str,
) -> dict[str, Any]:
    run_dir = Path(output_identity)
    if run_dir.exists():
        raise AssertionError(f"refusing to overwrite run evidence: {output_identity}")
    run_dir.mkdir(parents=True)

    scheduled_trips = demand["scheduled_trips"]
    scheduled_ids = {str(item["vehicle_id"]) for item in scheduled_trips}
    scheduled_departures = {
        str(item["vehicle_id"]): float(item["scheduled_departure_seconds"])
        for item in scheduled_trips
    }
    expected_routes = {
        str(item["vehicle_id"]): tuple(str(edge) for edge in item["edges"])
        for item in scheduled_trips
    }
    if len(scheduled_ids) != 180:
        raise AssertionError("frozen population is not 180 unique scheduled trips")

    started_utc = utc_now()
    started_counter = time.perf_counter()
    command = build_sumo_command(run_dir)
    label = run_id.lower().replace("-", "_")
    console_path = run_dir / "traci-console.log"
    failure_path = run_dir / "technical-failure.json"
    events_path = run_dir / "disruption-events.json"
    connection = None
    disruption_events: list[dict[str, Any]] = []
    applied = False
    restored = False
    emergency_restoration = False
    original_permissions: dict[str, list[str]] | None = None
    cutoff_permissions: dict[str, list[str]] | None = None
    close_errors: list[str] = []

    departed_events: dict[str, list[float]] = {}
    arrival_events: dict[str, list[float]] = {}
    teleport_start_events: dict[str, list[float]] = {}
    teleport_end_events: dict[str, list[float]] = {}
    route_mismatches: dict[str, dict[str, list[str]]] = {}
    queue_vehicle_seconds = 0.0
    per_trip_halting_seconds = {vehicle_id: 0.0 for vehicle_id in scheduled_ids}
    cutoff_active_ids: set[str] = set()
    cutoff_pending_ids: set[str] = set()
    final_simulation_time: float | None = None
    initial_tls_programs: dict[str, str] = {}
    current_tls_states: dict[str, str] = {}
    tls_state_transitions: dict[str, int] = {}
    tls_program_mutations: list[dict[str, object]] = []

    if sha256(RUNNER_PATH) != frozen_runner_hash:
        raise AssertionError("runner changed after its pre-execution hash was frozen")
    write_json_once(
        run_dir / "start-receipt.json",
        {
            "run_id": run_id,
            "attempt": RUN_ATTEMPT,
            "condition": "D0" if disrupted else "N0",
            "command": command,
            "input_sha256": input_hashes,
            "runner_sha256": frozen_runner_hash,
            "wall_clock_started_utc": started_utc,
            "status": "STARTED",
        },
    )

    try:
        with console_path.open("w", encoding="utf-8") as console:
            traci.start(command, label=label, stdout=console)
            connection = traci.getConnection(label)

            delta_t = float(connection.simulation.getDeltaT())
            if not math.isclose(delta_t, STEP_SECONDS, abs_tol=1e-12):
                raise AssertionError(f"unexpected simulation step length {delta_t}")

            tls_ids = sorted(connection.trafficlight.getIDList())
            if tls_ids != sorted(f"{column}{row}" for column in "ABC" for row in range(3)):
                raise AssertionError(f"unexpected TLS IDs: {tls_ids}")
            initial_tls_programs = {
                tls_id: connection.trafficlight.getProgram(tls_id) for tls_id in tls_ids
            }
            if set(initial_tls_programs.values()) != {"0"}:
                raise AssertionError(f"unexpected TLS programs: {initial_tls_programs}")
            current_tls_states = {
                tls_id: connection.trafficlight.getRedYellowGreenState(tls_id)
                for tls_id in tls_ids
            }
            tls_state_transitions = {tls_id: 0 for tls_id in tls_ids}

            original_permissions = lane_permissions(connection, DISRUPTED_LANE_ID)
            remaining_permissions = lane_permissions(connection, REMAINING_LANE_ID)
            if not passenger_allowed(original_permissions):
                raise AssertionError("selected disruption lane does not initially allow passenger")
            if not passenger_allowed(remaining_permissions):
                raise AssertionError("remaining lane does not allow passenger")

            trace_path = run_dir / "step-trace.csv"
            with trace_path.open("w", encoding="utf-8", newline="") as trace_handle:
                writer = csv.writer(trace_handle, lineterminator="\n")
                writer.writerow(
                    [
                        "simulation_time_seconds",
                        "active_vehicle_count",
                        "halting_vehicle_count_speed_below_0.1_mps",
                        "departed_step_count",
                        "arrived_step_count",
                        "starting_teleport_step_count",
                        "ending_teleport_step_count",
                        "disruption_active",
                    ]
                )

                for step_index in range(H_PILOT):
                    before_step = float(connection.simulation.getTime())
                    if not math.isclose(before_step, float(step_index), abs_tol=1e-12):
                        raise AssertionError(
                            f"step/time mismatch before step {step_index}: {before_step}"
                        )

                    if disrupted and step_index == DISRUPTION_START:
                        before_permissions = lane_permissions(connection, DISRUPTED_LANE_ID)
                        vehicles_on_lane = sorted(
                            connection.lane.getLastStepVehicleIDs(DISRUPTED_LANE_ID)
                        )
                        new_disallowed = sorted(
                            set(before_permissions["disallowed"]) | {PASSENGER_CLASS}
                        )
                        connection.lane.setDisallowed(DISRUPTED_LANE_ID, new_disallowed)
                        after_permissions = lane_permissions(connection, DISRUPTED_LANE_ID)
                        if passenger_allowed(after_permissions):
                            raise AssertionError("passenger restriction did not take effect")
                        disruption_events.append(
                            {
                                "event": "APPLY_ONE_LANE_LOSS_CAPACITY_PROXY",
                                "scheduled_step": DISRUPTION_START,
                                "observed_simulation_time_seconds": before_step,
                                "lane_id": DISRUPTED_LANE_ID,
                                "before_permissions": before_permissions,
                                "after_permissions": after_permissions,
                                "vehicles_on_lane_before_change": vehicles_on_lane,
                            }
                        )
                        applied = True

                    if disrupted and step_index == DISRUPTION_END:
                        if not applied or original_permissions is None:
                            raise AssertionError("restoration reached before validated application")
                        before_restore = lane_permissions(connection, DISRUPTED_LANE_ID)
                        connection.lane.setAllowed(
                            DISRUPTED_LANE_ID, original_permissions["allowed"]
                        )
                        connection.lane.setDisallowed(
                            DISRUPTED_LANE_ID, original_permissions["disallowed"]
                        )
                        after_restore = lane_permissions(connection, DISRUPTED_LANE_ID)
                        if after_restore != original_permissions:
                            raise AssertionError(
                                f"permission restoration mismatch: {after_restore}"
                            )
                        disruption_events.append(
                            {
                                "event": "RESTORE_ORIGINAL_PERMISSIONS",
                                "scheduled_step": DISRUPTION_END,
                                "observed_simulation_time_seconds": before_step,
                                "lane_id": DISRUPTED_LANE_ID,
                                "before_permissions": before_restore,
                                "after_permissions": after_restore,
                            }
                        )
                        restored = True

                    connection.simulationStep()
                    simulation_time = float(connection.simulation.getTime())
                    if not math.isclose(
                        simulation_time, float(step_index + 1), abs_tol=1e-12
                    ):
                        raise AssertionError(
                            f"step/time mismatch after step {step_index}: {simulation_time}"
                        )

                    departed_step = sorted(connection.simulation.getDepartedIDList())
                    arrived_step = sorted(connection.simulation.getArrivedIDList())
                    teleport_start_step = sorted(
                        connection.simulation.getStartingTeleportIDList()
                    )
                    teleport_end_step = sorted(
                        connection.simulation.getEndingTeleportIDList()
                    )

                    for vehicle_id in departed_step:
                        departed_events.setdefault(vehicle_id, []).append(simulation_time)
                        if vehicle_id in expected_routes:
                            actual_route = tuple(connection.vehicle.getRoute(vehicle_id))
                            if actual_route != expected_routes[vehicle_id]:
                                route_mismatches[vehicle_id] = {
                                    "expected": list(expected_routes[vehicle_id]),
                                    "actual": list(actual_route),
                                }
                    for vehicle_id in arrived_step:
                        arrival_events.setdefault(vehicle_id, []).append(simulation_time)
                    for vehicle_id in teleport_start_step:
                        teleport_start_events.setdefault(vehicle_id, []).append(simulation_time)
                    for vehicle_id in teleport_end_step:
                        teleport_end_events.setdefault(vehicle_id, []).append(simulation_time)

                    active_ids = sorted(connection.vehicle.getIDList())
                    halting_ids = [
                        vehicle_id
                        for vehicle_id in active_ids
                        if float(connection.vehicle.getSpeed(vehicle_id)) < 0.1
                    ]
                    queue_vehicle_seconds += len(halting_ids) * STEP_SECONDS
                    for vehicle_id in halting_ids:
                        if vehicle_id in per_trip_halting_seconds:
                            per_trip_halting_seconds[vehicle_id] += STEP_SECONDS

                    for tls_id in tls_ids:
                        observed_program = connection.trafficlight.getProgram(tls_id)
                        if observed_program != initial_tls_programs[tls_id]:
                            tls_program_mutations.append(
                                {
                                    "tls_id": tls_id,
                                    "simulation_time_seconds": simulation_time,
                                    "expected_program": initial_tls_programs[tls_id],
                                    "observed_program": observed_program,
                                }
                            )
                        observed_state = connection.trafficlight.getRedYellowGreenState(tls_id)
                        if observed_state != current_tls_states[tls_id]:
                            tls_state_transitions[tls_id] += 1
                            current_tls_states[tls_id] = observed_state

                    writer.writerow(
                        [
                            f"{simulation_time:.1f}",
                            len(active_ids),
                            len(halting_ids),
                            len(departed_step),
                            len(arrived_step),
                            len(teleport_start_step),
                            len(teleport_end_step),
                            "1"
                            if disrupted and DISRUPTION_START <= step_index < DISRUPTION_END
                            else "0",
                        ]
                    )

            final_simulation_time = float(connection.simulation.getTime())
            cutoff_active_ids = set(connection.vehicle.getIDList())
            cutoff_pending_ids = set(connection.simulation.getPendingVehicles())
            cutoff_permissions = lane_permissions(connection, DISRUPTED_LANE_ID)
            if cutoff_permissions != original_permissions:
                raise AssertionError("lane permissions differ from original at H_PILOT")
            if disrupted and (not applied or not restored):
                raise AssertionError("scheduled disruption lifecycle incomplete")
            if not disrupted and disruption_events:
                raise AssertionError("normal condition contains a disruption event")

    except Exception as exc:
        failure = {
            "status": "TECHNICAL_FAILURE",
            "run_id": run_id,
            "attempt": RUN_ATTEMPT,
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
            "wall_clock_detected_utc": utc_now(),
        }
        write_json(failure_path, failure)
        raise
    finally:
        if connection is not None:
            if disrupted and applied and not restored and original_permissions is not None:
                try:
                    connection.lane.setAllowed(
                        DISRUPTED_LANE_ID, original_permissions["allowed"]
                    )
                    connection.lane.setDisallowed(
                        DISRUPTED_LANE_ID, original_permissions["disallowed"]
                    )
                    emergency_restoration = True
                    disruption_events.append(
                        {
                            "event": "EMERGENCY_FINALLY_RESTORATION",
                            "lane_id": DISRUPTED_LANE_ID,
                            "observed_simulation_time_seconds": float(
                                connection.simulation.getTime()
                            ),
                            "after_permissions": lane_permissions(
                                connection, DISRUPTED_LANE_ID
                            ),
                        }
                    )
                except Exception as restore_error:
                    disruption_events.append(
                        {
                            "event": "EMERGENCY_FINALLY_RESTORATION_FAILED",
                            "lane_id": DISRUPTED_LANE_ID,
                            "error": str(restore_error),
                        }
                    )
            try:
                connection.close(wait=True)
            except Exception as close_error:
                close_errors.append(str(close_error))
                disruption_events.append(
                    {"event": "TRACI_CLOSE_ERROR", "error": str(close_error)}
                )
        write_json(events_path, {"events": disruption_events})

    finished_counter = time.perf_counter()
    finished_utc = utc_now()
    if final_simulation_time is None or not math.isclose(
        final_simulation_time, float(H_PILOT), abs_tol=1e-12
    ):
        raise AssertionError(f"simulation did not reach H_PILOT: {final_simulation_time}")

    tripinfo = parse_tripinfo(run_dir / "tripinfo.xml")
    tripinfo_ids = set(tripinfo)
    unknown_tripinfo_ids = sorted(tripinfo_ids - scheduled_ids)
    departed_ids = set(departed_events)
    raw_arrival_ids = set(arrival_events)
    teleport_ids = set(teleport_start_events)
    unknown_event_ids = sorted(
        (
            departed_ids
            | raw_arrival_ids
            | teleport_ids
            | set(teleport_end_events)
            | cutoff_active_ids
            | cutoff_pending_ids
        )
        - scheduled_ids
    )
    duplicate_event_ids = sorted(
        vehicle_id
        for event_map in (
            departed_events,
            arrival_events,
            teleport_start_events,
            teleport_end_events,
        )
        for vehicle_id, event_times in event_map.items()
        if len(event_times) != 1
    )

    terminal_teleported = teleport_ids & scheduled_ids
    terminal_arrived = (raw_arrival_ids & scheduled_ids) - terminal_teleported
    terminal_active = (
        (cutoff_active_ids & scheduled_ids)
        - terminal_teleported
        - terminal_arrived
    )
    terminal_not_departed = (
        (cutoff_pending_ids & scheduled_ids)
        - departed_ids
        - terminal_teleported
        - terminal_arrived
        - terminal_active
    )
    explained = (
        terminal_arrived
        | terminal_active
        | terminal_not_departed
        | terminal_teleported
    )
    failed_invalid = scheduled_ids - explained
    terminal_categories = {
        "arrived": terminal_arrived,
        "active": terminal_active,
        "not_departed": terminal_not_departed,
        "teleported": terminal_teleported,
        "failed_invalid": failed_invalid,
    }
    category_total = sum(len(values) for values in terminal_categories.values())
    category_overlap = sum(len(values) for values in terminal_categories.values()) - len(
        set().union(*terminal_categories.values())
    )

    integrity_errors: list[str] = []
    if unknown_tripinfo_ids:
        integrity_errors.append(f"unknown tripinfo IDs: {unknown_tripinfo_ids}")
    if unknown_event_ids:
        integrity_errors.append(f"unknown event IDs: {unknown_event_ids}")
    if duplicate_event_ids:
        integrity_errors.append(f"duplicate event IDs: {duplicate_event_ids}")
    if teleport_ids or teleport_end_events:
        integrity_errors.append("teleport events present despite disabled teleport policy")
    if set(teleport_end_events) - teleport_ids:
        integrity_errors.append("teleport-end event lacks a captured teleport-start event")
    if route_mismatches:
        integrity_errors.append(f"route mismatches: {sorted(route_mismatches)}")
    if tls_program_mutations:
        integrity_errors.append("traffic-light program identity changed")
    if failed_invalid:
        integrity_errors.append(f"unexplained disappeared IDs: {sorted(failed_invalid)}")
    if category_total != len(scheduled_ids) or category_overlap != 0:
        integrity_errors.append("terminal trip categories are not a disjoint partition")
    if not all(count > 0 for count in tls_state_transitions.values()):
        integrity_errors.append("one or more traffic lights did not cycle")
    if disrupted and emergency_restoration:
        integrity_errors.append("disruption required emergency restoration")
    if close_errors:
        integrity_errors.append(f"TraCI close errors: {close_errors}")

    ledger: dict[str, dict[str, Any]] = {}
    restricted_times: list[float] = []
    tripinfo_waiting_total = 0.0
    waiting_time_missing_ids: list[str] = []
    for trip in sorted(scheduled_trips, key=lambda item: str(item["vehicle_id"])):
        vehicle_id = str(trip["vehicle_id"])
        scheduled_departure = float(trip["scheduled_departure_seconds"])
        category = next(
            name for name, members in terminal_categories.items() if vehicle_id in members
        )
        record = tripinfo.get(vehicle_id)
        actual_departure = None if record is None else record["actual_departure_seconds"]
        valid_arrival = (
            None
            if category != "arrived" or record is None
            else record["arrival_seconds"]
        )
        if category == "arrived" and valid_arrival is None:
            integrity_errors.append(f"missing valid tripinfo arrival for {vehicle_id}")
            restricted_time = float(H_PILOT) - scheduled_departure
        else:
            metric_end = float(H_PILOT) if valid_arrival is None else min(
                float(valid_arrival), float(H_PILOT)
            )
            restricted_time = metric_end - scheduled_departure
        if restricted_time < 0 or restricted_time > H_PILOT - scheduled_departure:
            integrity_errors.append(f"invalid restricted time for {vehicle_id}")
        if actual_departure is not None and actual_departure < scheduled_departure:
            integrity_errors.append(f"actual departure precedes schedule for {vehicle_id}")
        if valid_arrival is not None:
            if actual_departure is None:
                integrity_errors.append(
                    f"valid arrival lacks actual departure for {vehicle_id}"
                )
            elif float(valid_arrival) < float(actual_departure):
                integrity_errors.append(
                    f"valid arrival precedes actual departure for {vehicle_id}"
                )
        restricted_times.append(restricted_time)

        waiting_time = None if record is None else record["waiting_time_seconds"]
        if vehicle_id in departed_ids and waiting_time is None:
            waiting_time_missing_ids.append(vehicle_id)
        if waiting_time is not None:
            tripinfo_waiting_total += float(waiting_time)
        ledger[vehicle_id] = {
            "route_id": trip["route_id"],
            "scheduled_departure_seconds": scheduled_departure,
            "actual_departure_seconds": actual_departure,
            "valid_non_teleported_arrival_seconds": valid_arrival,
            "terminal_category": category,
            "teleport_event": vehicle_id in teleport_ids,
            "raw_arrival_event": vehicle_id in raw_arrival_ids,
            "pending_at_cutoff": vehicle_id in cutoff_pending_ids,
            "restricted_trip_time_seconds": restricted_time,
            "observed_halting_seconds": per_trip_halting_seconds[vehicle_id],
            "sumo_tripinfo_waiting_time_seconds": waiting_time,
        }

    if waiting_time_missing_ids:
        integrity_errors.append(
            f"departed trips missing SUMO waiting time: {waiting_time_missing_ids}"
        )
    if not math.isclose(
        sum(per_trip_halting_seconds.values()), queue_vehicle_seconds, abs_tol=1e-12
    ):
        integrity_errors.append("per-trip halting sum does not equal queue burden")

    collision_count = count_collisions(run_dir / "collisions.xml")
    if collision_count:
        integrity_errors.append(f"collision records present: {collision_count}")
    simulator_errors = (run_dir / "simulator-errors.log").read_text(
        encoding="utf-8"
    ).strip()
    if simulator_errors:
        integrity_errors.append("simulator error log is non-empty")

    teleported_or_failed = len(terminal_teleported) + len(failed_invalid)
    unfinished = (
        len(terminal_active) + len(terminal_not_departed) + teleported_or_failed
    )
    restricted_mean = sum(restricted_times) / len(restricted_times)
    p95 = nearest_rank_p95(restricted_times)
    numeric_metrics = [
        queue_vehicle_seconds,
        tripinfo_waiting_total,
        restricted_mean,
        p95,
    ]
    if not all(math.isfinite(value) for value in numeric_metrics):
        integrity_errors.append("one or more metrics are NaN or infinite")

    metrics: dict[str, Any] = {
        "run_id": run_id,
        "condition_label": "DISRUPTED" if disrupted else "NORMAL",
        "attempt": RUN_ATTEMPT,
        "output_identity": output_identity,
        "scenario_seed": SEED,
        "simulation_start_seconds": 0.0,
        "simulation_end_seconds": final_simulation_time,
        "h_pilot_seconds": H_PILOT,
        "simulation_step_seconds": STEP_SECONDS,
        "scheduled_trips": len(scheduled_ids),
        "departed_trips": len(departed_ids),
        "arrived_trips": len(terminal_arrived),
        "active_trips_at_cutoff": len(terminal_active),
        "not_departed_trips_at_cutoff": len(terminal_not_departed),
        "teleported_terminal_trips": len(terminal_teleported),
        "failed_invalid_trips": len(failed_invalid),
        "teleported_or_failed_trips": teleported_or_failed,
        "unfinished_trips": unfinished,
        "unfinished_fraction": unfinished / len(scheduled_ids),
        "raw_arrival_events": len(raw_arrival_ids),
        "teleport_start_events": sum(map(len, teleport_start_events.values())),
        "teleport_end_events": sum(map(len, teleport_end_events.values())),
        "non_teleported_throughput_trips": len(terminal_arrived),
        "restricted_mean_trip_time_seconds": restricted_mean,
        "restricted_p95_trip_time_seconds_nearest_rank": p95,
        "cumulative_queue_vehicle_seconds": queue_vehicle_seconds,
        "sumo_tripinfo_waiting_time_seconds_total": tripinfo_waiting_total,
        "sumo_tripinfo_waiting_time_seconds_mean_all_scheduled": (
            tripinfo_waiting_total / len(scheduled_ids)
        ),
        "sumo_waiting_time_coverage_departed_trips": not waiting_time_missing_ids,
        "collision_count": collision_count,
        "fixed_time_programs_unchanged": not tls_program_mutations,
        "traffic_light_state_transition_counts": tls_state_transitions,
        "routes_unchanged": not route_mismatches,
        "trip_accounting_reconciled": category_total == len(scheduled_ids)
        and category_overlap == 0,
        "disruption_expected": disrupted,
        "disruption_application_validated": (
            applied and restored and cutoff_permissions == original_permissions
            if disrupted
            else None
        ),
        "permission_restoration_confirmed": (
            restored and cutoff_permissions == original_permissions
            if disrupted
            else None
        ),
        "integrity_errors": sorted(set(integrity_errors)),
        "integrity_pass": not integrity_errors,
        "wall_clock_started_utc": started_utc,
        "wall_clock_finished_utc": finished_utc,
        "simulation_wall_clock_runtime_seconds": finished_counter - started_counter,
    }

    write_json_once(run_dir / "vehicle-ledger.json", ledger)
    write_json_once(run_dir / "final-metrics.json", metrics)
    with (run_dir / "final-metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["metric", "value"])
        for key, value in sorted(metrics.items()):
            writer.writerow([key, json.dumps(value, sort_keys=True)])
    write_json_once(
        run_dir / "execution-receipt.json",
        {
            "run_id": run_id,
            "attempt": RUN_ATTEMPT,
            "condition": "D0" if disrupted else "N0",
            "command": command,
            "input_sha256": input_hashes,
            "runner_sha256": frozen_runner_hash,
            "wall_clock_started_utc": started_utc,
            "wall_clock_finished_utc": finished_utc,
            "simulation_wall_clock_runtime_seconds": finished_counter
            - started_counter,
            "status": "PASS" if not integrity_errors else "FAIL",
        },
    )
    if sha256(RUNNER_PATH) != frozen_runner_hash:
        raise AssertionError("runner changed during measured execution")
    if integrity_errors:
        raise AssertionError(f"run {run_id} integrity errors: {integrity_errors}")
    return metrics


def compare_pair(
    first_id: str,
    first_dir: Path,
    repeat_id: str,
    repeat_dir: Path,
    metrics_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    first_projection = scientific_metrics_projection(metrics_by_id[first_id])
    repeat_projection = scientific_metrics_projection(metrics_by_id[repeat_id])
    metrics_equal = first_projection == repeat_projection
    trace_equal = (first_dir / "step-trace.csv").read_bytes() == (
        repeat_dir / "step-trace.csv"
    ).read_bytes()
    ledger_equal = json.loads((first_dir / "vehicle-ledger.json").read_text()) == json.loads(
        (repeat_dir / "vehicle-ledger.json").read_text()
    )
    disruption_equal = json.loads(
        (first_dir / "disruption-events.json").read_text()
    ) == json.loads((repeat_dir / "disruption-events.json").read_text())
    return {
        "first": first_id,
        "repeat": repeat_id,
        "normalized_metrics_equal": metrics_equal,
        "step_trace_byte_equal": trace_equal,
        "vehicle_ledger_equal": ledger_equal,
        "disruption_events_equal": disruption_equal,
        "pass": metrics_equal and trace_equal and ledger_equal and disruption_equal,
    }


def finalize_bundle(summary: dict[str, Any]) -> None:
    inventory_path = ATTEMPT_CHECKS / "evidence-inventory.json"
    hash_path = ATTEMPT_CHECKS / "artifact-sha256.json"
    summary_path = ATTEMPT_CHECKS / "bundle-summary.json"
    artifacts_before_inventory = sorted(
        path.as_posix()
        for path in Path(".").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path not in {inventory_path, hash_path, summary_path}
    )
    artifacts_without_hash = sorted(
        set(artifacts_before_inventory)
        | {inventory_path.as_posix(), summary_path.as_posix()}
    )
    inventory = {
        "bundle_root_identity": "b0/2026-09-04_seed-20260904",
        "artifact_count_excluding_hash_manifest": len(artifacts_without_hash),
        "artifact_count_total_including_hash_manifest": len(artifacts_without_hash)
        + 1,
        "artifacts": artifacts_without_hash + [hash_path.as_posix()],
        "hash_manifest_self_hash_included": False,
    }
    write_json_once(inventory_path, inventory)
    artifacts_with_inventory = sorted(
        path for path in Path(".").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path not in {hash_path, summary_path}
    )
    hashes = {path.as_posix(): sha256(path) for path in artifacts_with_inventory}
    hashes[summary_path.as_posix()] = hashlib.sha256(
        json_text(summary).encode("utf-8")
    ).hexdigest()
    write_json_once(
        hash_path,
        {
            "sha256": dict(sorted(hashes.items())),
            "self_hash_included": False,
            "bundle_summary_hash_computed_before_final_summary_write": True,
        },
    )
    write_json_once(summary_path, summary)
    if sha256(summary_path) != hashes[summary_path.as_posix()]:
        raise AssertionError("final bundle summary hash mismatch")


def attempt_artifacts(excluded: set[Path]) -> list[Path]:
    artifacts: set[Path] = set()
    for _, output_identity, _ in RUN_PLAN:
        run_root = Path(output_identity)
        if run_root.exists():
            artifacts.update(path for path in run_root.rglob("*") if path.is_file())
    if ATTEMPT_CHECKS.exists():
        artifacts.update(
            path for path in ATTEMPT_CHECKS.rglob("*") if path.is_file()
        )
    return sorted(
        path
        for path in artifacts
        if path not in excluded and "__pycache__" not in path.parts
    )


def seal_failed_attempt() -> None:
    inventory_path = ATTEMPT_CHECKS / "failure-evidence-inventory.json"
    hash_path = ATTEMPT_CHECKS / "failure-artifact-sha256.json"
    if inventory_path.exists() or hash_path.exists():
        return
    existing = attempt_artifacts({inventory_path, hash_path})
    artifact_identities = sorted(
        {path.as_posix() for path in existing}
        | {inventory_path.as_posix(), hash_path.as_posix()}
    )
    write_json_once(
        inventory_path,
        {
            "bundle_root_identity": "b0/2026-09-04_seed-20260904",
            "run_attempt": RUN_ATTEMPT,
            "attempt_status": "INCOMPLETE_ATTEMPT",
            "artifact_count_including_hash_manifest": len(artifact_identities),
            "artifacts": artifact_identities,
            "hash_manifest_self_hash_included": False,
        },
    )
    files_to_hash = attempt_artifacts({hash_path})
    write_json_once(
        hash_path,
        {
            "sha256": {
                path.as_posix(): sha256(path) for path in files_to_hash
            },
            "self_hash_included": False,
        },
    )


def main() -> None:
    global ATTEMPT_INITIALIZED
    if Path.cwd().resolve() != BUNDLE_ROOT:
        raise AssertionError("runner must be launched from its frozen bundle root")
    verify_pristine_targets()
    ATTEMPT_CHECKS.mkdir(parents=True)
    ATTEMPT_INITIALIZED = True
    input_hashes = verify_frozen_inputs()
    demand = json.loads(DEMAND_MANIFEST.read_text(encoding="utf-8"))
    scenario = json.loads(SCENARIO_MANIFEST.read_text(encoding="utf-8"))
    disruption = json.loads(DISRUPTION_MANIFEST.read_text(encoding="utf-8"))
    contract_receipt = verify_frozen_contract(scenario, disruption, demand)
    write_json_once(
        ATTEMPT_CHECKS / "contract-reconciliation.json",
        contract_receipt,
    )
    runner_hash = sha256(RUNNER_PATH)
    runner_snapshot = ATTEMPT_CHECKS / "run_b0.executed.py"
    write_bytes_once(runner_snapshot, RUNNER_PATH.read_bytes())
    if sha256(runner_snapshot) != runner_hash:
        raise AssertionError("executed runner snapshot hash mismatch")
    write_json_once(
        ATTEMPT_CHECKS / "runner-sha256-before-execution.json",
        {
            "runner_sha256": runner_hash,
            "runner_snapshot_identity": runner_snapshot.as_posix(),
            "run_attempt": RUN_ATTEMPT,
        },
    )
    repository_before = repository_state()
    write_json_once(
        ATTEMPT_CHECKS / "repository-state-before.json",
        repository_before,
    )
    metrics_by_id: dict[str, dict[str, Any]] = {}

    for run_id, output_identity, disrupted in RUN_PLAN:
        metrics_by_id[run_id] = run_condition(
            run_id,
            output_identity,
            disrupted,
            input_hashes,
            demand,
            runner_hash,
        )

    repository_after = repository_state()
    if repository_after != repository_before:
        raise AssertionError("public repository state changed during B0 execution")
    write_json_once(
        ATTEMPT_CHECKS / "repository-state-after.json",
        repository_after,
    )

    normal_repeat = compare_pair(
        "N0",
        Path(RUN_PLAN[0][1]),
        "N0-R",
        Path(RUN_PLAN[2][1]),
        metrics_by_id,
    )
    disrupted_repeat = compare_pair(
        "D0",
        Path(RUN_PLAN[1][1]),
        "D0-R",
        Path(RUN_PLAN[3][1]),
        metrics_by_id,
    )
    determinism = {
        "normal": normal_repeat,
        "disrupted": disrupted_repeat,
        "pass": normal_repeat["pass"] and disrupted_repeat["pass"],
        "interpretation": "Exact repeats are reproducibility checks, not independent statistical seeds.",
    }
    write_json_once(
        ATTEMPT_CHECKS / "normalized-determinism-comparison.json", determinism
    )

    all_runs_pass = all(metrics["integrity_pass"] for metrics in metrics_by_id.values())
    status = "PASS" if all_runs_pass and determinism["pass"] else "FAIL"
    summary = {
        "b0_status": status,
        "run_attempt": RUN_ATTEMPT,
        "run_order": [run_id for run_id, _, _ in RUN_PLAN],
        "all_run_integrity_pass": all_runs_pass,
        "determinism_repeat_pass": determinism["pass"],
        "pre_empirical_boundary_preserved": True,
        "trip_accounting_reconciled": all(
            metrics["trip_accounting_reconciled"]
            for metrics in metrics_by_id.values()
        ),
        "restricted_trip_time_implemented": True,
        "public_git_modified": False,
        "repository_state_before_and_after_equal": repository_before
        == repository_after,
        "treatment_executed": False,
        "interpretation": "B0 substrate validation and scenario characterization only; not a test of the central hypothesis.",
    }
    finalize_bundle(summary)


def record_unhandled_failure(exception: BaseException) -> None:
    if not ATTEMPT_INITIALIZED:
        return
    failure_path = ATTEMPT_CHECKS / "bundle-failure.json"
    failure = {
        "status": "INCOMPLETE_ATTEMPT",
        "run_attempt": RUN_ATTEMPT,
        "exception_type": type(exception).__name__,
        "message": str(exception),
        "traceback": traceback.format_exc(),
        "wall_clock_detected_utc": utc_now(),
        "note": "Final scientific status requires review of the retained attempt evidence.",
    }
    try:
        if not failure_path.exists():
            write_json_once(failure_path, failure)
        repository_failure_path = ATTEMPT_CHECKS / "repository-state-after-failure.json"
        if not repository_failure_path.exists():
            try:
                repository_after_failure: dict[str, Any] = {
                    "read_succeeded": True,
                    "state": read_repository_state(),
                }
            except Exception as repository_error:
                repository_after_failure = {
                    "read_succeeded": False,
                    "error": str(repository_error),
                }
            write_json_once(repository_failure_path, repository_after_failure)
        seal_failed_attempt()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        record_unhandled_failure(error)
        raise
