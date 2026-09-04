#!/usr/bin/env python3
"""Run the isolated, baseline-only B0 demand-ladder calibration.

The runner derives its simulation loop from the frozen B0 runner with one
audited population-cardinality parameterization.  Network, signal, disruption,
metric, horizon and observer definitions remain byte-bound to prior evidence.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import traceback
import types
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping


CALIBRATION_IDENTITY = "B0_BASELINE_ONLY_DEMAND_CALIBRATION_V1"
CALIBRATED_SCENARIO_IDENTITY = "B0_CALIBRATED_SCENARIO_V1"
EVIDENCE_IDENTITY = "b0-calibration/2026-09-demand-ladder-v1"
DEMAND_ALGORITHM_IDENTITY = "B0_MULTIPLIED_SEEDED_ROUTE_SLOT_SCHEDULER_V1"
EXPECTED_REPOSITORY_SHA = "2a0da664c8f43a1e346c3c405fbff3fc40a78778"
EXPECTED_ORIGINAL_RUNNER_SHA256 = (
    "d4286193089a8062ae16e51e3dbaf8f26df6be11d43399d6fd998941b275ccab"
)
EXPECTED_ORIGINAL_NETWORK_SHA256 = (
    "49b2c7a89a72083b0f894c6b7083558f0120059122237d960a907bafbcf62dd2"
)
EXPECTED_ORIGINAL_ROUTE_SHA256 = (
    "12998402ad18f625440e85352a9c348882c7c504d18ded4ad9f42690322b276d"
)
EXPECTED_ORIGINAL_DISRUPTION_SHA256 = (
    "77df3a6504045f12815b6fe75ca7b00d370d568d1b5203d863f83385d536fb91"
)
EXPECTED_OBSERVER_SHA256 = (
    "dd582ab3011d3077c1ad1f63b95f26708813bf0628dcdee4bebda4c054a68d57"
)
OBSERVER_IDENTITY = "B0_EXPOSURE_DIAGNOSTIC_V1"
EXPECTED_ORIGINAL_TREE_OBJECT_COUNT = 97
EXPECTED_ORIGINAL_TREE_DIGEST = (
    "c34ff5d466056026d83f6dbd0dbe02300dedf2259a345b125d2149e893c3c145"
)
EXPECTED_DIAGNOSTIC_TREE_OBJECT_COUNT = 121
EXPECTED_DIAGNOSTIC_TREE_DIGEST = (
    "97a6388fad1f0b408088e0fcfea2d99f525e4a6ccfcab5612ae35a56db780977"
)

CALIBRATION_SEEDS = (20260904, 20260905, 20260906)
FROZEN_SUMO_SEED = 20260904
DEMAND_LADDER = (("2X", 2), ("3X", 3), ("4X", 4), ("5X", 5))
H_PILOT = 1500
STEP_SECONDS = 1.0
DISRUPTION_START = 300
DISRUPTION_END = 600
MONITORED_EDGE = "A1B1"
RESTRICTED_LANE = "A1B1_0"
SURVIVING_LANE = "A1B1_1"
PASSENGER_CLASS = "passenger"
RUN_ATTEMPT = 1
BLOCK_COUNT = 15
BLOCK_SECONDS = 60

ROUTES = (
    ("row0_east", "left0A0 A0B0 B0C0 C0right0"),
    ("row0_west", "right0C0 C0B0 B0A0 A0left0"),
    ("row1_east", "left1A1 A1B1 B1C1 C1right1"),
    ("row1_west", "right1C1 C1B1 B1A1 A1left1"),
    ("row2_east", "left2A2 A2B2 B2C2 C2right2"),
    ("row2_west", "right2C2 C2B2 B2A2 A2left2"),
    ("colA_north", "bottom0A0 A0A1 A1A2 A2top0"),
    ("colA_south", "top0A2 A2A1 A1A0 A0bottom0"),
    ("colB_north", "bottom1B0 B0B1 B1B2 B2top1"),
    ("colB_south", "top1B2 B2B1 B1B0 B0bottom1"),
    ("colC_north", "bottom2C0 C0C1 C1C2 C2top2"),
    ("colC_south", "top2C2 C2C1 C1C0 C0bottom2"),
)
VTYPE_ATTRIBUTES = {
    "id": "passenger_deterministic",
    "vClass": "passenger",
    "accel": "2.6",
    "decel": "4.5",
    "sigma": "0",
    "length": "5.0",
    "minGap": "2.5",
    "maxSpeed": "13.89",
}

BUNDLE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = BUNDLE_ROOT.parents[2]
LOCAL_EVIDENCE_ROOT = REPOSITORY_ROOT / ".local-evidence"
ORIGINAL_ROOT = LOCAL_EVIDENCE_ROOT / "b0" / "2026-09-04_seed-20260904"
DIAGNOSTIC_ROOT = (
    LOCAL_EVIDENCE_ROOT
    / "b0-diagnostic"
    / "2026-09-04_seed-20260904"
    / "exposure-v1"
)
ORIGINAL_RUNNER_PATH = ORIGINAL_ROOT / "run_b0.py"
ORIGINAL_NETWORK_PATH = ORIGINAL_ROOT / "inputs" / "b0-grid-3x3.net.xml"
ORIGINAL_ROUTE_PATH = ORIGINAL_ROOT / "inputs" / "b0-fixed-routes.rou.xml"
ORIGINAL_DISRUPTION_PATH = ORIGINAL_ROOT / "inputs" / "disruption-specification.json"
VALIDATED_OBSERVER_PATH = (
    DIAGNOSTIC_ROOT / "checks" / "attempt-002" / "exposure_observer.executed.py"
)
CONTRACT_PATH = Path("contracts/calibration-contract.json")
RUNNER_PATH = Path("run_calibration.py")
NETWORK_PATH = Path("inputs/network/b0-grid-3x3.net.xml")
OBSERVER_PATH = Path("inputs/observer/exposure_observer.py")
DISRUPTION_PATH = Path("inputs/disruption-specification.json")
ATTEMPT_CHECKS = Path("checks/attempt-001")

CURRENT_ROUTE_FILE: Path | None = None
CURRENT_SEED: int | None = None
ATTEMPT_INITIALIZED = False
FROZEN_INPUT_HASHES: dict[str, str] = {}


class CalibrationInconclusive(RuntimeError):
    """A completed run cannot support an unambiguous calibration decision."""


class CalibrationIntegrityFailure(RuntimeError):
    """Executed evidence contradicts a frozen integrity requirement."""


class CalibrationBlocked(RuntimeError):
    """The local environment cannot perform a required calibration operation."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_text(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def write_json_once(path: Path, value: object) -> None:
    write_bytes_once(path, json_text(value).encode("utf-8"))


def relative_identity(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()


def load_parameterized_baseline_runner() -> tuple[types.ModuleType, dict[str, Any]]:
    source = ORIGINAL_RUNNER_PATH.read_bytes()
    if sha256_bytes(source) != EXPECTED_ORIGINAL_RUNNER_SHA256:
        raise AssertionError("frozen original B0 runner hash mismatch")
    text = source.decode("utf-8")
    original_guard = (
        "    if len(scheduled_ids) != 180:\n"
        "        raise AssertionError(\"frozen population is not 180 unique scheduled trips\")"
    )
    parameterized_guard = (
        "    if len(scheduled_ids) != int(demand[\"scheduled_trip_count\"]):\n"
        "        raise AssertionError(\"population does not match the frozen candidate demand manifest\")"
    )
    if text.count(original_guard) != 1:
        raise AssertionError("expected exactly one baseline population guard")
    derived = text.replace(original_guard, parameterized_guard, 1)
    module_name = "frozen_b0_runner_parameterized_for_calibration"
    module = types.ModuleType(module_name)
    module.__file__ = str(ORIGINAL_RUNNER_PATH)
    module.__package__ = None
    sys.modules[module_name] = module
    exec(compile(derived, str(ORIGINAL_RUNNER_PATH), "exec"), module.__dict__)
    receipt = {
        "source_runner_sha256": EXPECTED_ORIGINAL_RUNNER_SHA256,
        "transformation_identity": "POPULATION_CARDINALITY_GUARD_PARAMETERIZATION_ONLY",
        "replacement_count": 1,
        "derived_source_sha256": sha256_bytes(derived.encode("utf-8")),
        "metric_logic_changed": False,
        "simulation_loop_changed": False,
    }
    return module, receipt


BASE, BASE_DERIVATION_RECEIPT = load_parameterized_baseline_runner()


def load_module_from_source(path: Path, module_name: str) -> types.ModuleType:
    source = path.read_bytes()
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    module.__package__ = None
    sys.modules[module_name] = module
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def git_output(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def repository_state() -> dict[str, Any]:
    relative_bundle = BUNDLE_ROOT.relative_to(REPOSITORY_ROOT).as_posix()
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", relative_bundle],
        cwd=REPOSITORY_ROOT,
        check=False,
    ).returncode == 0
    state = {
        "repository_sha": git_output("rev-parse", "HEAD"),
        "branch": git_output("branch", "--show-current"),
        "worktree_and_index_clean": not git_output(
            "status", "--porcelain=v1", "--untracked-files=all"
        ),
        "local_evidence_bundle_ignored": ignored,
    }
    expected = {
        "repository_sha": EXPECTED_REPOSITORY_SHA,
        "branch": "main",
        "worktree_and_index_clean": True,
        "local_evidence_bundle_ignored": True,
    }
    if state != expected:
        raise AssertionError(f"unexpected public repository state: {state}")
    return state


def tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def snapshot_digest(snapshot: Mapping[str, str]) -> str:
    return sha256_bytes(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def validate_contract() -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    expected = {
        "calibration_identity": CALIBRATION_IDENTITY,
        "evidence_identity": EVIDENCE_IDENTITY,
        "seeds": list(CALIBRATION_SEEDS),
        "ladder": [label for label, _ in DEMAND_LADDER],
        "algorithm": DEMAND_ALGORITHM_IDENTITY,
        "network": "B0_GRID_3X3_V1",
        "event": [DISRUPTION_START, DISRUPTION_END],
        "h_pilot": H_PILOT,
        "observer": contract.get("frozen_source_bindings", {}).get(
            "observer_identity"
        ),
        "observer_sha256": contract.get("frozen_source_bindings", {}).get(
            "observer_sha256"
        ),
        "first_qualifying": "FIRST_QUALIFYING",
    }
    actual = {
        "calibration_identity": contract.get("calibration_identity"),
        "evidence_identity": contract.get("evidence_identity"),
        "seeds": contract.get("calibration_seeds"),
        "ladder": [item["label"] for item in contract.get("demand_ladder", [])],
        "algorithm": contract.get("demand_generation", {}).get(
            "algorithm_identity"
        ),
        "network": contract.get("scientific_configuration", {}).get(
            "network_identity"
        ),
        "event": [
            contract.get("scientific_configuration", {}).get(
                "disruption_start_inclusive"
            ),
            contract.get("scientific_configuration", {}).get(
                "disruption_end_exclusive"
            ),
        ],
        "h_pilot": contract.get("scientific_configuration", {}).get(
            "h_pilot_seconds"
        ),
        "observer": OBSERVER_IDENTITY,
        "observer_sha256": EXPECTED_OBSERVER_SHA256,
        "first_qualifying": contract.get("selection_rule", {}).get("rule"),
    }
    if actual != expected:
        raise AssertionError(
            f"calibration contract differs from runner: expected={expected}, actual={actual}"
        )
    research_boundary = contract["research_boundary"]
    required_boundary = {
        "baseline_only": True,
        "calibration_seeds_excluded_from_final_confirmatory_treatment_estimate": True,
        "calibration_seed_reuse_requires_later_preregistered_justification": True,
        "capacity_conditioned_treatment_exists": False,
        "future_treatment_results_may_influence_selection": False,
        "rl_executed": False,
    }
    if any(
        research_boundary.get(key) != value
        for key, value in required_boundary.items()
    ):
        raise AssertionError("pretreatment boundary is not closed")
    if contract["calibration_location"] != {
        "corridor_edges": ["A1B1", "B1A1"],
        "future_headline_heldout_location_eligible": False,
        "role": "CALIBRATION_SEEN_LOCATION",
    }:
        raise AssertionError("calibration seen-location contract mismatch")
    qualification = contract["qualification_contract"]
    thresholds = {
        "n0_completion_fraction_minimum": 0.99,
        "d0_completion_fraction_minimum": 0.95,
        "d0_exposure_count_minimum": 10,
        "d0_mean_trip_time_increase_seconds_minimum": 1.0,
        "d0_queue_burden_relative_increase_minimum": 0.05,
    }
    if any(qualification.get(key) != value for key, value in thresholds.items()):
        raise AssertionError("qualification thresholds differ from predeclared values")
    bindings = contract["frozen_source_bindings"]
    expected_bindings = {
        "disruption_source_sha256": EXPECTED_ORIGINAL_DISRUPTION_SHA256,
        "network_sha256": EXPECTED_ORIGINAL_NETWORK_SHA256,
        "observer_identity": OBSERVER_IDENTITY,
        "observer_sha256": EXPECTED_OBSERVER_SHA256,
        "original_b0_route_sha256": EXPECTED_ORIGINAL_ROUTE_SHA256,
        "original_b0_runner_sha256": EXPECTED_ORIGINAL_RUNNER_SHA256,
        "observer_byte_exact_reuse_required": True,
    }
    if bindings != expected_bindings:
        raise AssertionError("frozen source bindings differ from approved evidence")
    demand_generation = contract["demand_generation"]
    if (
        demand_generation.get("departure_time_serialization") != "INTEGER_SECONDS"
        or demand_generation.get("simulator_random_mode") is not False
        or demand_generation.get("simulator_seed") != FROZEN_SUMO_SEED
        or demand_generation.get("seed_role")
        != "DEPARTURE_ROUTE_TO_SLOT_ASSIGNMENT_ONLY"
    ):
        raise AssertionError("demand-only calibration boundary is not explicit")
    if qualification.get("comparators_are_inclusive") is not True:
        raise AssertionError("qualification comparator boundary is not frozen")
    if contract["demand_ladder"] != [
        {"label": label, "multiplier": multiplier, "scheduled_trips": 180 * multiplier}
        for label, multiplier in DEMAND_LADDER
    ]:
        raise AssertionError("demand ladder counts or multipliers differ")
    if contract["conditions_per_candidate_seed"] != ["N0-CAL", "D0-CAL"]:
        raise AssertionError("condition pair differs from baseline-only contract")
    if contract["scientific_configuration"] != {
        "disruption_end_exclusive": DISRUPTION_END,
        "disruption_start_inclusive": DISRUPTION_START,
        "dynamic_rerouting": False,
        "fixed_time_tls_program_seconds": 68,
        "h_pilot_seconds": H_PILOT,
        "monitored_edge": MONITORED_EDGE,
        "network_identity": "B0_GRID_3X3_V1",
        "passenger_class": PASSENGER_CLASS,
        "restricted_lane": RESTRICTED_LANE,
        "simulation_step_seconds": 1,
        "surviving_lane": SURVIVING_LANE,
    }:
        raise AssertionError("scientific configuration differs from B0 substrate")
    if contract["selection_rule"].get("sequence") != [
        label for label, _ in DEMAND_LADDER
    ] or contract["selection_rule"].get(
        "higher_levels_after_first_qualifier_are_prohibited"
    ) is not True:
        raise AssertionError("first-qualifying stop rule is not fully frozen")
    recovery = contract["recovery_diagnostic"]
    if (
        recovery.get("post_restoration_first_sample_seconds") != 601
        or recovery.get("near_zero_absolute_vehicle_threshold") != 1
        or recovery.get("statuses")
        != [
            "RECOVERY_SIGNAL_OBSERVED",
            "NO_RECOVERY_SIGNAL",
            "NOT_IDENTIFIABLE",
        ]
        or recovery.get("classification_is_not_final_dissertation_recovery_definition")
        is not True
    ):
        raise AssertionError("recovery diagnostic semantics are not fully frozen")
    repeat = contract["selected_deterministic_repeat"]
    if (
        repeat.get("seed") != CALIBRATION_SEEDS[0]
        or repeat.get("conditions") != ["N0-CAL-R", "D0-CAL-R"]
        or repeat.get("exact_equality_required") is not True
    ):
        raise AssertionError("selected-scenario repeat contract differs")
    if contract["effect_threshold_boundary"] != {
        "dissertation_delta_frozen": False,
        "pilot_mean_trip_time_gate_is_delta": False,
        "pilot_queue_gate_is_delta": False,
        "pilot_thresholds_are_scenario_sensitivity_gates_only": True,
    }:
        raise AssertionError("dissertation effect-threshold boundary is not open")
    required_integrity = {
        "activation_and_restoration_directly_observed": True,
        "all_metrics_finite": True,
        "all_scheduled_trips_accounted": True,
        "fixed_time_tls_unchanged": True,
        "invalid_or_failed_routes_maximum": 0,
        "no_rerouting": True,
        "passenger_post_activation_restricted_lane_entries_maximum": 0,
        "routes_unchanged": True,
        "sumo_collisions_maximum": 0,
        "unexplained_simulator_errors_maximum": 0,
        "unexpected_permission_transition_count_maximum": 0,
    }
    if qualification.get("integrity") != required_integrity:
        raise AssertionError("integrity qualification contract differs")
    return contract


def demand_paths(label: str, seed: int) -> tuple[Path, Path]:
    root = Path("inputs/demand") / label.lower() / f"seed-{seed}"
    return root / "fixed-routes.rou.xml", root / "demand-manifest.json"


def build_demand(multiplier: int, seed: int) -> tuple[bytes, dict[str, Any]]:
    if multiplier not in {1, 2, 3, 4, 5}:
        raise ValueError("multiplier must be in the closed test/calibration range 1..5")
    if seed not in CALIBRATION_SEEDS:
        raise ValueError("seed is outside the frozen calibration seed set")

    rng = random.Random(seed)
    scheduled: list[dict[str, Any]] = []
    root = ET.Element("routes")
    ET.SubElement(root, "vType", VTYPE_ATTRIBUTES)
    for route_id, edges in ROUTES:
        ET.SubElement(root, "route", {"id": route_id, "edges": edges})

    vehicle_index = 0
    for block in range(BLOCK_COUNT):
        block_routes = list(ROUTES) * multiplier
        rng.shuffle(block_routes)
        for slot, (route_id, edges) in enumerate(block_routes):
            depart = block * BLOCK_SECONDS + (5 * slot) // multiplier
            vehicle_id = f"veh_{vehicle_index:04d}"
            ET.SubElement(
                root,
                "vehicle",
                {
                    "id": vehicle_id,
                    "type": "passenger_deterministic",
                    "route": route_id,
                    "depart": str(depart),
                    "departLane": "best",
                    "departSpeed": "max",
                },
            )
            scheduled.append(
                {
                    "vehicle_id": vehicle_id,
                    "scheduled_departure_seconds": depart,
                    "route_id": route_id,
                    "edges": edges.split(),
                    "block_index": block,
                    "slot_index_within_block": slot,
                }
            )
            vehicle_index += 1

    ET.indent(root, space="  ")
    buffer = io.BytesIO()
    ET.ElementTree(root).write(buffer, encoding="utf-8", xml_declaration=True)
    route_bytes = buffer.getvalue()
    route_counts = Counter(str(item["route_id"]) for item in scheduled)
    event_scheduled = [
        item
        for item in scheduled
        if MONITORED_EDGE in item["edges"]
        and DISRUPTION_START
        <= int(item["scheduled_departure_seconds"])
        < DISRUPTION_END
    ]
    manifest = {
        "calibration_identity": CALIBRATION_IDENTITY,
        "algorithm_identity": DEMAND_ALGORITHM_IDENTITY,
        "scenario_seed": seed,
        "demand_multiplier": multiplier,
        "generation_algorithm": (
            "15 sixty-second blocks; shuffle list(ROUTES)*multiplier once per "
            "block using one continuous random.Random(seed); slot k departs at "
            "block*60 + floor(5*k/multiplier)"
        ),
        "demand_window_seconds": {"start_inclusive": 0, "end_exclusive": 900},
        "scheduled_trip_count": len(scheduled),
        "route_count": len(ROUTES),
        "route_topology_sha256": sha256_bytes(
            json.dumps(ROUTES, separators=(",", ":")).encode("utf-8")
        ),
        "trips_per_route": dict(sorted(route_counts.items())),
        "scheduled_structural_A1B1_trip_count": sum(
            MONITORED_EDGE in item["edges"] for item in scheduled
        ),
        "scheduled_structural_A1B1_departures_during_event": len(event_scheduled),
        "routes_fixed_before_simulation": True,
        "dynamic_rerouting": False,
        "scheduled_trips": scheduled,
    }
    return route_bytes, manifest


def validate_demand(
    route_path: Path, manifest_path: Path, multiplier: int, seed: int
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    route_root = ET.parse(route_path).getroot()
    if route_root.tag != "routes":
        raise AssertionError("candidate demand root element is not routes")
    if any(child.tag not in {"vType", "route", "vehicle"} for child in route_root):
        raise AssertionError("candidate demand contains an unapproved element")
    forbidden_tags = {
        "flow",
        "trip",
        "rerouter",
        "routeDistribution",
        "person",
    }
    if any(node.tag in forbidden_tags for node in route_root.iter()):
        raise AssertionError("candidate demand contains non-fixed or rerouting demand")
    vtypes = route_root.findall("vType")
    if len(vtypes) != 1 or vtypes[0].attrib != VTYPE_ATTRIBUTES:
        raise AssertionError("candidate vehicle type differs from frozen type")
    route_nodes = route_root.findall("route")
    vehicle_nodes = route_root.findall("vehicle")
    expected_route_definitions = [(route, edges) for route, edges in ROUTES]
    actual_route_definitions = [
        (node.attrib["id"], node.attrib["edges"]) for node in route_nodes
    ]
    if actual_route_definitions != expected_route_definitions:
        raise AssertionError("candidate route definitions differ from frozen routes")
    expected_count = 180 * multiplier
    expected_per_route = 15 * multiplier
    if manifest["scheduled_trip_count"] != expected_count:
        raise AssertionError("candidate manifest population mismatch")
    if len(vehicle_nodes) != expected_count:
        raise AssertionError("candidate XML population mismatch")
    if set(manifest["trips_per_route"].values()) != {expected_per_route}:
        raise AssertionError("candidate routes are not globally balanced")
    expected_topology_sha = sha256_bytes(
        json.dumps(ROUTES, separators=(",", ":")).encode("utf-8")
    )
    if manifest.get("route_topology_sha256") != expected_topology_sha:
        raise AssertionError("candidate route-topology hash mismatch")
    departures = [int(node.attrib["depart"]) for node in vehicle_nodes]
    if departures != sorted(departures) or len(departures) != len(set(departures)):
        raise AssertionError("candidate departures are not unique and ordered")
    if departures[0] != 0 or departures[-1] >= 900:
        raise AssertionError("candidate departure window mismatch")
    if manifest["scenario_seed"] != seed or manifest["demand_multiplier"] != multiplier:
        raise AssertionError("candidate demand identity mismatch")
    manifest_by_id = {
        item["vehicle_id"]: item for item in manifest["scheduled_trips"]
    }
    expected_vehicle_attributes = {
        "id",
        "type",
        "route",
        "depart",
        "departLane",
        "departSpeed",
    }
    for index, node in enumerate(vehicle_nodes):
        if set(node.attrib) != expected_vehicle_attributes:
            raise AssertionError("candidate vehicle attributes differ from frozen schema")
        if node.attrib["id"] != f"veh_{index:04d}":
            raise AssertionError("candidate vehicle IDs are not contiguous")
        if (
            node.attrib["type"] != VTYPE_ATTRIBUTES["id"]
            or node.attrib["departLane"] != "best"
            or node.attrib["departSpeed"] != "max"
        ):
            raise AssertionError("candidate vehicle behavior attributes changed")
        item = manifest_by_id.get(node.attrib["id"])
        if item is None:
            raise AssertionError("candidate XML vehicle missing from manifest")
        if (
            node.attrib["route"] != item["route_id"]
            or int(node.attrib["depart"]) != item["scheduled_departure_seconds"]
        ):
            raise AssertionError("candidate XML/manifest record mismatch")
    block_counts = Counter(value // BLOCK_SECONDS for value in departures)
    if set(block_counts.values()) != {12 * multiplier} or len(block_counts) != 15:
        raise AssertionError("candidate demand is not balanced by block")
    for block in range(BLOCK_COUNT):
        block_items = [
            item for item in manifest["scheduled_trips"] if item["block_index"] == block
        ]
        if Counter(item["route_id"] for item in block_items) != Counter(
            {route_id: multiplier for route_id, _ in ROUTES}
        ):
            raise AssertionError("candidate routes are not balanced within each block")
        expected_block_departures = [
            block * BLOCK_SECONDS + (5 * slot) // multiplier
            for slot in range(12 * multiplier)
        ]
        if [item["scheduled_departure_seconds"] for item in block_items] != (
            expected_block_departures
        ):
            raise AssertionError("candidate departure slots differ from frozen formula")
    rebuilt_bytes, rebuilt_manifest = build_demand(multiplier, seed)
    if route_path.read_bytes() != rebuilt_bytes:
        raise AssertionError("candidate route file differs from independent reconstruction")
    comparable_manifest = dict(manifest)
    comparable_manifest.pop("route_file_identity", None)
    comparable_manifest.pop("route_file_sha256", None)
    if comparable_manifest != rebuilt_manifest:
        raise AssertionError("candidate demand manifest differs from reconstruction")
    if manifest.get("route_file_sha256") != sha256(route_path):
        raise AssertionError("candidate route file self-binding mismatch")
    return {
        "status": "PASS",
        "seed": seed,
        "multiplier": multiplier,
        "scheduled_trip_count": expected_count,
        "trips_per_route": expected_per_route,
        "trips_per_block": 12 * multiplier,
        "max_departure_seconds": departures[-1],
        "route_file_sha256": sha256(route_path),
        "manifest_sha256": sha256(manifest_path),
        "scheduled_structural_A1B1_trip_count": manifest[
            "scheduled_structural_A1B1_trip_count"
        ],
        "scheduled_structural_A1B1_departures_during_event": manifest[
            "scheduled_structural_A1B1_departures_during_event"
        ],
    }


def prepare_frozen_inputs() -> dict[str, Any]:
    if sha256(ORIGINAL_NETWORK_PATH) != EXPECTED_ORIGINAL_NETWORK_SHA256:
        raise AssertionError("original network hash mismatch")
    if sha256(ORIGINAL_ROUTE_PATH) != EXPECTED_ORIGINAL_ROUTE_SHA256:
        raise AssertionError("original 1X route hash mismatch")
    if sha256(VALIDATED_OBSERVER_PATH) != EXPECTED_OBSERVER_SHA256:
        raise AssertionError("validated observer hash mismatch")
    if sha256(ORIGINAL_DISRUPTION_PATH) != EXPECTED_ORIGINAL_DISRUPTION_SHA256:
        raise AssertionError("original disruption specification hash mismatch")
    contract = validate_contract()

    write_bytes_once(NETWORK_PATH, ORIGINAL_NETWORK_PATH.read_bytes())
    write_bytes_once(OBSERVER_PATH, VALIDATED_OBSERVER_PATH.read_bytes())
    write_bytes_once(DISRUPTION_PATH, ORIGINAL_DISRUPTION_PATH.read_bytes())
    if sha256(NETWORK_PATH) != EXPECTED_ORIGINAL_NETWORK_SHA256:
        raise AssertionError("calibration network copy differs from B0")
    if sha256(OBSERVER_PATH) != EXPECTED_OBSERVER_SHA256:
        raise AssertionError("calibration observer copy differs from validated observer")

    demand_receipts: dict[str, Any] = {}
    for label, multiplier in DEMAND_LADDER:
        demand_receipts[label] = {}
        for seed in CALIBRATION_SEEDS:
            route_path, manifest_path = demand_paths(label, seed)
            route_bytes, manifest = build_demand(multiplier, seed)
            manifest["route_file_identity"] = route_path.as_posix()
            manifest["route_file_sha256"] = sha256_bytes(route_bytes)
            write_bytes_once(route_path, route_bytes)
            write_json_once(manifest_path, manifest)
            demand_receipts[label][str(seed)] = validate_demand(
                route_path, manifest_path, multiplier, seed
            )

    one_x_bytes, _ = build_demand(1, 20260904)
    if sha256_bytes(one_x_bytes) != EXPECTED_ORIGINAL_ROUTE_SHA256:
        raise AssertionError("calibration scheduler does not reproduce frozen 1X XML")

    global FROZEN_INPUT_HASHES
    frozen_paths = [
        CONTRACT_PATH,
        RUNNER_PATH,
        NETWORK_PATH,
        OBSERVER_PATH,
        DISRUPTION_PATH,
        Path("tests/test_calibration_logic.py"),
    ]
    for label, _ in DEMAND_LADDER:
        for seed in CALIBRATION_SEEDS:
            frozen_paths.extend(demand_paths(label, seed))
    FROZEN_INPUT_HASHES = {
        path.as_posix(): sha256(path) for path in sorted(frozen_paths)
    }
    receipt = {
        "status": "PASS",
        "frozen_before_first_simulation": True,
        "calibration_identity": CALIBRATION_IDENTITY,
        "contract_sha256": sha256(CONTRACT_PATH),
        "network_identity": "B0_GRID_3X3_V1",
        "network_sha256": sha256(NETWORK_PATH),
        "network_matches_original_b0": True,
        "disruption_sha256": sha256(DISRUPTION_PATH),
        "observer_identity": OBSERVER_IDENTITY,
        "observer_sha256": sha256(OBSERVER_PATH),
        "observer_matches_validated_attempt_002": True,
        "baseline_runner_derivation": BASE_DERIVATION_RECEIPT,
        "one_x_scheduler_backward_compatibility_sha256": sha256_bytes(one_x_bytes),
        "one_x_scheduler_reproduces_original_route_file": True,
        "demand_generation_algorithm": contract["demand_generation"],
        "demand_receipts": demand_receipts,
        "all_preexecution_frozen_input_sha256": FROZEN_INPUT_HASHES,
    }
    write_json_once(ATTEMPT_CHECKS / "pre-execution-input-freeze.json", receipt)
    return receipt


def attribute_call_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def imported_top_level_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def static_noninterference_receipt() -> dict[str, Any]:
    forbidden = {
        "changeLane",
        "changeLaneRelative",
        "rerouteEffort",
        "rerouteTraveltime",
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
    observer_calls = attribute_call_names(OBSERVER_PATH)
    calibration_calls = attribute_call_names(RUNNER_PATH)
    baseline_calls = attribute_call_names(ORIGINAL_RUNNER_PATH)
    observer_forbidden = sorted(observer_calls & forbidden)
    calibration_forbidden = sorted(calibration_calls & forbidden)
    prohibited_learning_modules = {
        "torch",
        "tensorflow",
        "gym",
        "gymnasium",
        "ray",
        "stable_baselines3",
    }
    learning_imports = sorted(
        (
            imported_top_level_modules(RUNNER_PATH)
            | imported_top_level_modules(ORIGINAL_RUNNER_PATH)
            | imported_top_level_modules(OBSERVER_PATH)
        )
        & prohibited_learning_modules
    )
    baseline_rerouting_or_control_calls = sorted(baseline_calls & forbidden)
    baseline_permission_mutators = sorted(
        baseline_calls & {"setAllowed", "setDisallowed"}
    )
    passed = (
        not observer_forbidden
        and not calibration_forbidden
        and not baseline_rerouting_or_control_calls
        and baseline_permission_mutators == ["setAllowed", "setDisallowed"]
        and not learning_imports
    )
    receipt = {
        "status": "PASS" if passed else "FAIL",
        "observer_sha256": sha256(OBSERVER_PATH),
        "observer_identity": OBSERVER_IDENTITY,
        "observer_forbidden_control_calls": observer_forbidden,
        "calibration_runner_forbidden_control_calls": calibration_forbidden,
        "baseline_runner_forbidden_control_calls": baseline_rerouting_or_control_calls,
        "baseline_runner_permission_mutators": baseline_permission_mutators,
        "learning_framework_imports": learning_imports,
        "control_scope_description": (
            "Frozen restricted-lane activation/restoration only"
        ),
        "observer_source_modified": False,
        "dynamic_rerouting": False,
        "rl_or_treatment_framework_imports_present": bool(learning_imports),
    }
    if not passed:
        raise AssertionError(f"static non-interference check failed: {receipt}")
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
        raise AssertionError(f"calibration preflight tests failed: {receipt}")
    return receipt


def configure_base_runner(seed: int, route_path: Path) -> None:
    global CURRENT_ROUTE_FILE, CURRENT_SEED
    CURRENT_ROUTE_FILE = route_path
    CURRENT_SEED = seed
    # The inherited metric field records the calibration (demand) seed.  The
    # SUMO command itself remains bound to FROZEN_SUMO_SEED with random=false.
    BASE.SEED = seed
    BASE.H_PILOT = H_PILOT
    BASE.STEP_SECONDS = STEP_SECONDS
    BASE.RUN_ATTEMPT = RUN_ATTEMPT
    BASE.DISRUPTION_START = DISRUPTION_START
    BASE.DISRUPTION_END = DISRUPTION_END
    BASE.DISRUPTED_EDGE_ID = MONITORED_EDGE
    BASE.DISRUPTED_LANE_ID = RESTRICTED_LANE
    BASE.REMAINING_LANE_ID = SURVIVING_LANE
    BASE.PASSENGER_CLASS = PASSENGER_CLASS
    BASE.RUNNER_PATH = RUNNER_PATH
    BASE.EXPECTED_REPOSITORY_SHA = EXPECTED_REPOSITORY_SHA
    BASE.BUNDLE_ROOT = BUNDLE_ROOT
    BASE.build_sumo_command = build_calibration_sumo_command


def build_calibration_sumo_command(run_dir: Path) -> list[str]:
    if CURRENT_ROUTE_FILE is None or CURRENT_SEED is None:
        raise AssertionError("calibration run inputs are not configured")
    return calibration_sumo_command(run_dir, CURRENT_ROUTE_FILE)


def calibration_sumo_command(run_dir: Path, route_path: Path) -> list[str]:
    return [
        "sumo",
        "--net-file",
        NETWORK_PATH.as_posix(),
        "--route-files",
        route_path.as_posix(),
        "--begin",
        "0",
        "--end",
        str(H_PILOT),
        "--step-length",
        "1",
        "--time-to-teleport",
        "-1",
        "--waiting-time-memory",
        "1501",
        "--max-depart-delay",
        "-1",
        "--seed",
        str(FROZEN_SUMO_SEED),
        "--random",
        "false",
        "--device.rerouting.probability",
        "0",
        "--person-device.rerouting.probability",
        "0",
        "--no-step-log",
        "true",
        "--duration-log.statistics",
        "true",
        "--xml-validation",
        "never",
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


def run_input_hashes(route_path: Path, manifest_path: Path) -> dict[str, str]:
    identities = (
        NETWORK_PATH,
        route_path,
        manifest_path,
        DISRUPTION_PATH,
        OBSERVER_PATH,
        CONTRACT_PATH,
    )
    if not FROZEN_INPUT_HASHES:
        raise AssertionError("pre-execution input hashes are not frozen")
    return {
        path.as_posix(): FROZEN_INPUT_HASHES[path.as_posix()]
        for path in identities
    }


def verify_input_hashes(expected: Mapping[str, str]) -> None:
    mismatches = {
        identity: {"expected": value, "actual": sha256(Path(identity))}
        for identity, value in expected.items()
        if not Path(identity).is_file() or sha256(Path(identity)) != value
    }
    if mismatches:
        raise AssertionError(f"calibration input hash mismatch: {mismatches}")


def verify_all_frozen_input_hashes() -> None:
    if not FROZEN_INPUT_HASHES:
        raise AssertionError("pre-execution frozen input map is unavailable")
    verify_input_hashes(FROZEN_INPUT_HASHES)


def run_observed_condition(
    *,
    observer_module: types.ModuleType,
    run_id: str,
    run_dir: Path,
    disrupted: bool,
    seed: int,
    route_path: Path,
    manifest_path: Path,
    demand: dict[str, Any],
    runner_hash: str,
) -> dict[str, Any]:
    configure_base_runner(seed, route_path)
    verify_all_frozen_input_hashes()
    input_hashes = run_input_hashes(route_path, manifest_path)
    verify_input_hashes(input_hashes)
    structural_ids = {
        str(item["vehicle_id"])
        for item in demand["scheduled_trips"]
        if MONITORED_EDGE in item["edges"]
    }
    observer = observer_module.ExposureObserver(
        run_id=run_id,
        monitored_edges={MONITORED_EDGE: (RESTRICTED_LANE, SURVIVING_LANE)},
        passenger_class=PASSENGER_CLASS,
        event_start_seconds=DISRUPTION_START,
        event_end_seconds=DISRUPTION_END,
        pre_activation_time_seconds=DISRUPTION_START,
    )
    original_get_connection = BASE.traci.getConnection
    connection_requests = 0

    def observed_get_connection(label: str) -> Any:
        nonlocal connection_requests
        connection_requests += 1
        return observer_module.ObservedConnection(original_get_connection(label), observer)

    BASE.traci.getConnection = observed_get_connection
    try:
        try:
            metrics = BASE.run_condition(
                run_id,
                run_dir.as_posix(),
                disrupted,
                input_hashes,
                demand,
                runner_hash,
            )
        except BaseException:
            if run_dir.is_dir():
                partial_path = run_dir / "partial-exposure-events.json"
                if not partial_path.exists():
                    write_json_once(partial_path, observer.events_payload())
            raise
        if connection_requests != 1:
            raise AssertionError(
                f"observer connection count differs from one: {connection_requests}"
            )
        try:
            observer.finalize(H_PILOT)
        except AssertionError as error:
            raise CalibrationInconclusive(
                f"validated observer could not finalize at H_PILOT: {error}"
            ) from error
        if sha256(OBSERVER_PATH) != EXPECTED_OBSERVER_SHA256:
            raise AssertionError("observer changed during calibration execution")
        write_json_once(run_dir / "exposure-events.json", observer.events_payload())
        write_json_once(
            run_dir / "pre-event-occupancy.json", observer.pre_activation_payload()
        )
        write_json_once(
            run_dir / "exposure-summary.json", observer.summary_payload(structural_ids)
        )
        write_json_once(
            run_dir / "observer-execution-receipt.json",
            {
                "observer_identity": OBSERVER_IDENTITY,
                "observer_sha256": sha256(OBSERVER_PATH),
                "full_horizon_observed": True,
                "connection_wrapper_count": connection_requests,
                "source_modified": False,
            },
        )
        write_json_once(
            run_dir / "calibration-run-binding.json",
            {
                "calibration_identity": CALIBRATION_IDENTITY,
                "demand_calibration_seed": seed,
                "legacy_final_metrics_scenario_seed_semantics": (
                    "DEMAND_CALIBRATION_SEED; SUMO RNG SEED IS SEPARATELY FROZEN"
                ),
                "sumo_random_mode": False,
                "sumo_rng_seed": FROZEN_SUMO_SEED,
                "route_file_identity": route_path.as_posix(),
                "route_file_sha256": input_hashes[route_path.as_posix()],
                "demand_manifest_identity": manifest_path.as_posix(),
                "demand_manifest_sha256": input_hashes[manifest_path.as_posix()],
                "only_demand_schedule_differs_between_calibration_seeds": True,
            },
        )
        verify_input_hashes(input_hashes)
        verify_all_frozen_input_hashes()
        return metrics
    finally:
        BASE.traci.getConnection = original_get_connection


def numeric_values_are_finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, Mapping):
        return all(numeric_values_are_finite(item) for item in value.values())
    if isinstance(value, Iterable):
        return all(numeric_values_are_finite(item) for item in value)
    return True


def event_count(
    events: Iterable[Mapping[str, Any]], name: str, timestamp: float, lane_id: str
) -> int:
    return sum(
        item.get("event") == name
        and item.get("lane_id") == lane_id
        and math.isclose(
            float(item.get("observed_at_seconds", math.nan)), timestamp, abs_tol=1e-12
        )
        for item in events
    )


def command_option(command: list[str], option: str) -> str | None:
    positions = [index for index, value in enumerate(command) if value == option]
    if len(positions) != 1 or positions[0] + 1 >= len(command):
        return None
    return command[positions[0] + 1]


def command_preserves_calibration_boundary(
    run_dir: Path, route_path: Path
) -> dict[str, Any]:
    receipt = json.loads((run_dir / "execution-receipt.json").read_text())
    command = receipt["command"]
    expected = {
        "--net-file": NETWORK_PATH.as_posix(),
        "--route-files": route_path.as_posix(),
        "--begin": "0",
        "--end": str(H_PILOT),
        "--step-length": "1",
        "--time-to-teleport": "-1",
        "--waiting-time-memory": "1501",
        "--max-depart-delay": "-1",
        "--seed": str(FROZEN_SUMO_SEED),
        "--random": "false",
        "--device.rerouting.probability": "0",
        "--person-device.rerouting.probability": "0",
    }
    actual = {key: command_option(command, key) for key in expected}
    allowed_rerouting_options = {
        "--device.rerouting.probability",
        "--person-device.rerouting.probability",
    }
    unexpected_rerouting_options = sorted(
        value
        for value in command
        if value.startswith("--")
        and "rerout" in value.lower()
        and value not in allowed_rerouting_options
    )
    exact_command = calibration_sumo_command(run_dir, route_path)
    return {
        "pass": (
            actual == expected
            and not unexpected_rerouting_options
            and command == exact_command
        ),
        "expected_options": expected,
        "actual_options": actual,
        "unexpected_rerouting_options": unexpected_rerouting_options,
        "exact_command_match": command == exact_command,
    }


def exact_observer_permission_lifecycle(
    events: Iterable[Mapping[str, Any]], disrupted: bool
) -> dict[str, Any]:
    permission_names = {
        "RESTRICTION_ACTIVATION",
        "RESTORATION",
        "PERMISSION_CHANGE",
    }
    observed = [
        {
            "event": item.get("event"),
            "time": item.get("observed_at_seconds"),
            "lane_id": item.get("lane_id"),
        }
        for item in events
        if item.get("event") in permission_names
    ]
    expected = (
        [
            {
                "event": "RESTRICTION_ACTIVATION",
                "time": DISRUPTION_START,
                "lane_id": RESTRICTED_LANE,
            },
            {
                "event": "RESTORATION",
                "time": DISRUPTION_END,
                "lane_id": RESTRICTED_LANE,
            },
        ]
        if disrupted
        else []
    )
    return {"pass": observed == expected, "observed": observed, "expected": expected}


def exact_raw_disruption_lifecycle(run_dir: Path, disrupted: bool) -> dict[str, Any]:
    raw = json.loads((run_dir / "disruption-events.json").read_text())["events"]
    observed = [
        {
            "event": item.get("event"),
            "time": item.get("observed_simulation_time_seconds"),
            "lane_id": item.get("lane_id"),
        }
        for item in raw
    ]
    expected = (
        [
            {
                "event": "APPLY_ONE_LANE_LOSS_CAPACITY_PROXY",
                "time": DISRUPTION_START,
                "lane_id": RESTRICTED_LANE,
            },
            {
                "event": "RESTORE_ORIGINAL_PERMISSIONS",
                "time": DISRUPTION_END,
                "lane_id": RESTRICTED_LANE,
            },
        ]
        if disrupted
        else []
    )
    return {"pass": observed == expected, "observed": observed, "expected": expected}


def trace_integrity(
    run_dir: Path, metrics: Mapping[str, Any], disrupted: bool
) -> dict[str, Any]:
    expected_header = [
        "simulation_time_seconds",
        "active_vehicle_count",
        "halting_vehicle_count_speed_below_0.1_mps",
        "departed_step_count",
        "arrived_step_count",
        "starting_teleport_step_count",
        "ending_teleport_step_count",
        "disruption_active",
    ]
    errors: list[str] = []
    rows: list[dict[str, str]] = []
    try:
        with (run_dir / "step-trace.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != expected_header:
                errors.append("TRACE_HEADER_MISMATCH")
            rows = list(reader)
        timestamps = [float(row["simulation_time_seconds"]) for row in rows]
        if timestamps != [float(value) for value in range(1, H_PILOT + 1)]:
            errors.append("TRACE_TIME_GRID_MISMATCH")
        queue_total = sum(
            int(row["halting_vehicle_count_speed_below_0.1_mps"]) for row in rows
        )
        if exact_fraction(queue_total) != exact_fraction(
            metrics["cumulative_queue_vehicle_seconds"]
        ):
            errors.append("TRACE_QUEUE_TOTAL_MISMATCH")
        if sum(int(row["departed_step_count"]) for row in rows) != int(
            metrics["departed_trips"]
        ):
            errors.append("TRACE_DEPARTURE_TOTAL_MISMATCH")
        if sum(int(row["arrived_step_count"]) for row in rows) != int(
            metrics["raw_arrival_events"]
        ):
            errors.append("TRACE_ARRIVAL_TOTAL_MISMATCH")
        if sum(int(row["starting_teleport_step_count"]) for row in rows) != int(
            metrics["teleport_start_events"]
        ):
            errors.append("TRACE_TELEPORT_START_TOTAL_MISMATCH")
        if sum(int(row["ending_teleport_step_count"]) for row in rows) != int(
            metrics["teleport_end_events"]
        ):
            errors.append("TRACE_TELEPORT_END_TOTAL_MISMATCH")
        actual_disruption_times = [
            int(float(row["simulation_time_seconds"]))
            for row in rows
            if row["disruption_active"] == "1"
        ]
        expected_disruption_times = (
            list(range(DISRUPTION_START + 1, DISRUPTION_END + 1))
            if disrupted
            else []
        )
        if actual_disruption_times != expected_disruption_times:
            errors.append("TRACE_DISRUPTION_WINDOW_MISMATCH")
        if any(
            row["disruption_active"] not in {"0", "1"}
            or int(row["active_vehicle_count"]) < 0
            or int(row["halting_vehicle_count_speed_below_0.1_mps"]) < 0
            for row in rows
        ):
            errors.append("TRACE_INVALID_COUNT_OR_FLAG")
    except (OSError, ValueError, KeyError) as error:
        errors.append(f"TRACE_PARSE_FAILURE:{type(error).__name__}")
    return {
        "pass": not errors,
        "row_count": len(rows),
        "errors": sorted(set(errors)),
    }


def vehroute_matches_manifest(
    path: Path, demand: Mapping[str, Any], expected_departed_count: int
) -> dict[str, Any]:
    expected = {
        str(item["vehicle_id"]): tuple(str(edge) for edge in item["edges"])
        for item in demand["scheduled_trips"]
    }
    errors: list[str] = []
    observed: dict[str, tuple[str, ...]] = {}
    try:
        root = ET.parse(path).getroot()
        if root.tag != "routes":
            errors.append("VEHROUTE_ROOT_MISMATCH")
        for vehicle in root.findall("vehicle"):
            vehicle_id = vehicle.attrib.get("id", "")
            route_nodes = vehicle.findall("route")
            if vehicle_id in observed:
                errors.append(f"DUPLICATE_VEHROUTE_ID:{vehicle_id}")
                continue
            if len(route_nodes) != 1:
                errors.append(f"NON_UNIQUE_VEHROUTE:{vehicle_id}")
                continue
            if set(route_nodes[0].attrib) != {"edges"}:
                errors.append(f"VEHROUTE_REPLACEMENT_METADATA_PRESENT:{vehicle_id}")
            observed[vehicle_id] = tuple(route_nodes[0].attrib.get("edges", "").split())
        unknown = sorted(set(observed) - set(expected))
        if unknown:
            errors.append(f"UNKNOWN_VEHROUTE_IDS:{','.join(unknown)}")
        if len(observed) != expected_departed_count:
            errors.append("VEHROUTE_DEPARTED_COUNT_MISMATCH")
        mismatches = sorted(
            vehicle_id
            for vehicle_id in set(observed) & set(expected)
            if observed[vehicle_id] != expected[vehicle_id]
        )
        if mismatches:
            errors.append(f"VEHROUTE_EDGE_MISMATCH:{','.join(mismatches)}")
    except (OSError, ET.ParseError) as error:
        errors.append(f"VEHROUTE_PARSE_FAILURE:{type(error).__name__}")
    return {"pass": not errors, "errors": errors, "vehicle_count": len(observed)}


def empty_collision_artifact_is_valid(path: Path) -> bool:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return False
    return root.tag == "collisions" and not root.findall("collision")


def ledger_matches_manifest_and_metrics(
    ledger: Mapping[str, Any],
    demand: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    expected = {
        str(item["vehicle_id"]): item for item in demand["scheduled_trips"]
    }
    errors: list[str] = []
    if set(ledger) != set(expected):
        errors.append("LEDGER_ID_SET_MISMATCH")
    for vehicle_id in sorted(set(ledger) & set(expected)):
        record = ledger[vehicle_id]
        trip = expected[vehicle_id]
        if record.get("route_id") != trip["route_id"]:
            errors.append(f"LEDGER_ROUTE_MISMATCH:{vehicle_id}")
        if exact_fraction(record.get("scheduled_departure_seconds")) != exact_fraction(
            trip["scheduled_departure_seconds"]
        ):
            errors.append(f"LEDGER_DEPARTURE_MISMATCH:{vehicle_id}")
    if ledger:
        restricted = sorted(
            exact_fraction(item["restricted_trip_time_seconds"])
            for item in ledger.values()
        )
        restricted_total = sum(restricted, Fraction(0, 1))
        if not math.isclose(
            float(restricted_total / len(restricted)),
            float(metrics["restricted_mean_trip_time_seconds"]),
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            errors.append("LEDGER_RESTRICTED_MEAN_MISMATCH")
        p95_rank = math.ceil(Fraction(95, 100) * len(restricted))
        if not math.isclose(
            float(restricted[p95_rank - 1]),
            float(metrics["restricted_p95_trip_time_seconds_nearest_rank"]),
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            errors.append("LEDGER_RESTRICTED_P95_MISMATCH")
        waiting_total = sum(
            (
                exact_fraction(value)
                for value in (
                    item.get("sumo_tripinfo_waiting_time_seconds")
                    for item in ledger.values()
                )
                if value is not None
            ),
            Fraction(0, 1),
        )
        if not math.isclose(
            float(waiting_total),
            float(metrics["sumo_tripinfo_waiting_time_seconds_total"]),
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            errors.append("LEDGER_NATIVE_WAITING_TOTAL_MISMATCH")
    return {"pass": not errors, "errors": sorted(set(errors))}


def load_trace(path: Path) -> dict[float, int]:
    values: dict[float, int] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            timestamp = float(row["simulation_time_seconds"])
            if timestamp in values:
                raise AssertionError("duplicate queue-trace timestamp")
            values[timestamp] = int(
                row["halting_vehicle_count_speed_below_0.1_mps"]
            )
    expected = [float(value) for value in range(1, H_PILOT + 1)]
    if sorted(values) != expected:
        raise CalibrationInconclusive("queue trace does not cover exactly 1..H_PILOT")
    return values


def recovery_diagnostic(
    n0_dir: Path, d0_dir: Path, output_path: Path | None = None
) -> dict[str, Any]:
    try:
        n0 = load_trace(n0_dir / "step-trace.csv")
        d0 = load_trace(d0_dir / "step-trace.csv")
    except (CalibrationInconclusive, OSError, ValueError, KeyError) as error:
        return {
            "status": "NOT_IDENTIFIABLE",
            "reason": f"INVALID_OR_INCOMPLETE_TRACE:{type(error).__name__}",
            "final_dissertation_recovery_definition_created": False,
        }
    if set(n0) != set(d0):
        return {"status": "NOT_IDENTIFIABLE", "reason": "TRACE_TIME_MISMATCH"}
    samples = [
        (timestamp, d0[timestamp] - n0[timestamp])
        for timestamp in sorted(n0)
        if timestamp > DISRUPTION_END
    ]
    if not samples:
        return {"status": "NOT_IDENTIFIABLE", "reason": "NO_POST_RESTORATION_SAMPLES"}
    positive_excess_samples = [
        (timestamp, max(0, signed_value))
        for timestamp, signed_value in samples
    ]
    trace_identity: str | None = None
    trace_sha256: str | None = None
    if output_path is not None:
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(
            [
                "simulation_time_seconds",
                "signed_d0_minus_n0_queue_vehicles",
                "positive_excess_queue_vehicles",
            ]
        )
        for (timestamp, signed), (_, positive) in zip(
            samples, positive_excess_samples, strict=True
        ):
            writer.writerow([f"{timestamp:.1f}", signed, positive])
        write_bytes_once(output_path, buffer.getvalue().encode("utf-8"))
        trace_identity = output_path.as_posix()
        trace_sha256 = sha256(output_path)
    peak_value = max(value for _, value in positive_excess_samples)
    peak_time = next(
        (
            timestamp
            for timestamp, value in positive_excess_samples
            if value == peak_value
        ),
        None,
    )
    if peak_value <= 0:
        peak_time = None
        declined = False
        returned_near_zero = False
        near_zero_time = None
        status = "NO_RECOVERY_SIGNAL"
    else:
        later = [
            (timestamp, value)
            for timestamp, value in positive_excess_samples
            if peak_time is not None and timestamp > peak_time
        ]
        declined = any(value < peak_value for _, value in later)
        near_zero = [
            (timestamp, value)
            for timestamp, value in later
            if timestamp < H_PILOT and value <= 1 and value < peak_value
        ]
        returned_near_zero = bool(near_zero)
        near_zero_time = None if not near_zero else near_zero[0][0]
        status = "RECOVERY_SIGNAL_OBSERVED" if declined else "NO_RECOVERY_SIGNAL"
    return {
        "status": status,
        "maximum_positive_excess_queue_vehicles": peak_value,
        "earliest_peak_time_seconds": peak_time,
        "excess_queue_at_h_pilot_vehicles": samples[-1][1],
        "declines_after_peak": declined,
        "returns_to_zero_or_near_zero_before_h_pilot": returned_near_zero,
        "first_zero_or_near_zero_time_after_peak_seconds": near_zero_time,
        "near_zero_absolute_vehicle_threshold": 1,
        "first_post_restoration_sample_seconds": samples[0][0],
        "post_restoration_sample_count": len(samples),
        "signed_excess_trace_sha256": sha256_bytes(
            json.dumps(samples, separators=(",", ":")).encode("utf-8")
        ),
        "positive_excess_trace_sha256": sha256_bytes(
            json.dumps(
                positive_excess_samples, separators=(",", ":")
            ).encode("utf-8")
        ),
        "derived_excess_queue_trace_identity": trace_identity,
        "derived_excess_queue_trace_sha256": trace_sha256,
        "final_dissertation_recovery_definition_created": False,
    }


def select_unique_A1B1_visit(
    summary: Mapping[str, Any], vehicle_id: str, *, during_only: bool
) -> dict[str, Any] | None:
    per_vehicle = summary.get("per_vehicle", {}).get(vehicle_id)
    if not isinstance(per_vehicle, Mapping):
        return None
    visits = [
        visit
        for visit in per_vehicle.get("edge_visits", [])
        if visit["edge_id"] == MONITORED_EDGE
        and (
            not during_only
            or visit.get("entry_period") == "DURING"
        )
    ]
    return visits[0] if len(visits) == 1 else None


def paired_local_response(n0_dir: Path, d0_dir: Path) -> dict[str, Any]:
    n0_summary = json.loads((n0_dir / "exposure-summary.json").read_text())
    d0_summary = json.loads((d0_dir / "exposure-summary.json").read_text())
    n0_ledger = json.loads((n0_dir / "vehicle-ledger.json").read_text())
    d0_ledger = json.loads((d0_dir / "vehicle-ledger.json").read_text())
    exposed_ids = d0_summary["unique_edge_entries"]["during"]
    comparisons: list[dict[str, Any]] = []
    unidentifiable: list[dict[str, Any]] = []
    for vehicle_id in exposed_ids:
        n0_visit = select_unique_A1B1_visit(
            n0_summary, vehicle_id, during_only=False
        )
        d0_visit = select_unique_A1B1_visit(
            d0_summary, vehicle_id, during_only=True
        )
        if n0_visit is None or d0_visit is None:
            unidentifiable.append(
                {
                    "vehicle_id": vehicle_id,
                    "reason": "MISSING_OR_NON_UNIQUE_A1B1_VISIT",
                    "n0_visit_identified": n0_visit is not None,
                    "d0_event_visit_identified": d0_visit is not None,
                }
            )
            continue
        n0_arrival = n0_ledger[vehicle_id]["valid_non_teleported_arrival_seconds"]
        d0_arrival = d0_ledger[vehicle_id]["valid_non_teleported_arrival_seconds"]
        arrival_delta = (
            None
            if n0_arrival is None or d0_arrival is None
            else float(d0_arrival) - float(n0_arrival)
        )
        edge_time_delta = float(d0_visit["observed_edge_time_seconds"]) - float(
            n0_visit["observed_edge_time_seconds"]
        )
        edge_halting_delta = float(d0_visit["observed_halting_seconds"]) - float(
            n0_visit["observed_halting_seconds"]
        )
        physical_response = (
            edge_time_delta > 0
            or edge_halting_delta > 0
            or (arrival_delta is not None and arrival_delta > 0)
        )
        comparisons.append(
            {
                "vehicle_id": vehicle_id,
                "n0_edge_entry_observed_at_seconds": n0_visit[
                    "entry_observed_at_seconds"
                ],
                "d0_edge_entry_observed_at_seconds": d0_visit[
                    "entry_observed_at_seconds"
                ],
                "n0_edge_time_seconds": n0_visit["observed_edge_time_seconds"],
                "d0_edge_time_seconds": d0_visit["observed_edge_time_seconds"],
                "edge_time_delta_seconds": edge_time_delta,
                "n0_edge_halting_seconds": n0_visit["observed_halting_seconds"],
                "d0_edge_halting_seconds": d0_visit["observed_halting_seconds"],
                "edge_halting_delta_seconds": edge_halting_delta,
                "n0_final_arrival_seconds": n0_arrival,
                "d0_final_arrival_seconds": d0_arrival,
                "final_arrival_delta_seconds": arrival_delta,
                "final_arrival_comparison_identifiable": arrival_delta is not None,
                "local_physical_response": physical_response,
            }
        )
        if not physical_response and arrival_delta is None:
            unidentifiable.append(
                {
                    "vehicle_id": vehicle_id,
                    "reason": "NO_EDGE_WITNESS_AND_FINAL_ARRIVAL_COMPARISON_UNAVAILABLE",
                    "n0_arrival_seconds": n0_arrival,
                    "d0_arrival_seconds": d0_arrival,
                }
            )
    positive_witnesses = [
        item["vehicle_id"] for item in comparisons if item["local_physical_response"]
    ]
    if positive_witnesses:
        status = "PASS"
        observed: bool | None = True
    elif unidentifiable:
        status = "NOT_IDENTIFIABLE"
        observed = None
    else:
        status = "FAIL"
        observed = False
    return {
        "status": status,
        "exposed_vehicle_count": len(exposed_ids),
        "exposed_vehicle_ids": exposed_ids,
        "comparisons": comparisons,
        "unidentifiable_comparisons": unidentifiable,
        "vehicles_with_local_physical_response": positive_witnesses,
        "local_physical_response_observed": observed,
    }


def exact_fraction(value: Any) -> Fraction:
    """Convert an observed scalar without losing an exact decimal boundary."""

    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        return Fraction(int(value), 1)
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite value cannot be compared exactly")
        return Fraction(str(value))
    return Fraction(str(value))


def qualification_from_observations(observation: Mapping[str, Any]) -> dict[str, Any]:
    checks = {
        "integrity": bool(observation["integrity_pass"]),
        "n0_completion_at_least_0_99": exact_fraction(
            observation["n0_completion_fraction"]
        )
        >= Fraction(99, 100),
        "n0_zero_teleports": int(observation["n0_teleport_events"]) == 0,
        "d0_completion_at_least_0_95": exact_fraction(
            observation["d0_completion_fraction"]
        )
        >= Fraction(95, 100),
        "d0_zero_teleports": int(observation["d0_teleport_events"]) == 0,
        "d0_exposure_at_least_10": int(observation["d0_exposure_count"]) >= 10,
        "mean_trip_time_increase_at_least_1_second": exact_fraction(
            observation["mean_trip_time_difference_seconds"]
        )
        >= Fraction(1, 1),
        "queue_burden_increase_at_least_5_percent": (
            observation["queue_burden_relative_change"] is not None
            and exact_fraction(observation["queue_burden_relative_change"])
            >= Fraction(1, 20)
        ),
        "local_physical_response_observed": (
            None
            if observation["local_physical_response_observed"] is None
            else bool(observation["local_physical_response_observed"])
        ),
    }
    if observation["queue_burden_relative_change"] is None:
        checks["queue_burden_increase_at_least_5_percent"] = None
    definite_failures = [
        key for key, passed in checks.items() if passed is False and key != "integrity"
    ]
    unknown_checks = [key for key, passed in checks.items() if passed is None]
    if not checks["integrity"]:
        status = "INTEGRITY_FAILURE"
    elif definite_failures:
        status = "DOES_NOT_QUALIFY"
    elif unknown_checks:
        status = "NOT_IDENTIFIABLE"
    else:
        status = "QUALIFIES"
    return {
        "status": status,
        "qualifies": status == "QUALIFIES",
        "checks": checks,
        "failed_checks": sorted(
            definite_failures + ([] if checks["integrity"] else ["integrity"])
        ),
        "not_identifiable_checks": sorted(unknown_checks),
    }


def aggregate_seed_qualification_statuses(statuses: Iterable[str]) -> str:
    values = list(statuses)
    if not values:
        raise ValueError("at least one seed qualification status is required")
    allowed = {
        "QUALIFIES",
        "DOES_NOT_QUALIFY",
        "NOT_IDENTIFIABLE",
        "INTEGRITY_FAILURE",
    }
    if any(value not in allowed for value in values):
        raise ValueError(f"unexpected seed qualification status: {values}")
    if "INTEGRITY_FAILURE" in values:
        return "INTEGRITY_FAILURE"
    if "DOES_NOT_QUALIFY" in values:
        return "DOES_NOT_QUALIFY"
    if "NOT_IDENTIFIABLE" in values:
        return "NOT_IDENTIFIABLE"
    return "QUALIFIES"


def first_qualifying_decision(
    candidate_status_by_label: Mapping[str, str]
) -> dict[str, Any]:
    evaluated: list[str] = []
    selected = "NONE"
    decision = "NO_QUALIFYING_DEMAND_LEVEL"
    for label, _ in DEMAND_LADDER:
        if label not in candidate_status_by_label:
            break
        status = candidate_status_by_label[label]
        evaluated.append(label)
        if status == "INTEGRITY_FAILURE":
            decision = "FAIL"
            break
        if status == "NOT_IDENTIFIABLE":
            decision = "INCONCLUSIVE"
            break
        if status == "QUALIFIES":
            selected = label
            decision = "SELECTED"
            break
        if status != "DOES_NOT_QUALIFY":
            raise ValueError(f"unexpected candidate status for {label}: {status}")
    else:
        decision = "NO_QUALIFYING_DEMAND_LEVEL"
    ladder_labels = [label for label, _ in DEMAND_LADDER]
    return {
        "decision": decision,
        "selected_level": selected,
        "evaluated_levels": evaluated,
        "not_run_levels": ladder_labels[len(evaluated) :],
    }


def descriptive_values(values: Iterable[float]) -> dict[str, Any]:
    observed = [float(value) for value in values]
    return {
        "n": len(observed),
        "mean": statistics.fmean(observed) if observed else None,
        "sample_standard_deviation": (
            statistics.stdev(observed) if len(observed) >= 2 else None
        ),
        "minimum": min(observed) if observed else None,
        "maximum": max(observed) if observed else None,
        "inferential_test_performed": False,
    }


def candidate_descriptive_summary(
    seed_results: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    values = list(seed_results.values())
    queue_changes = [
        item["queue_burden_vehicle_seconds"]["relative_change"]
        for item in values
        if item["queue_burden_vehicle_seconds"]["relative_change"] is not None
    ]
    return {
        "d0_exposure_count": descriptive_values(
            item["exposure"]["d0_unique_A1B1_entries_during_event"]
            for item in values
        ),
        "restricted_mean_trip_time_d0_minus_n0_seconds": descriptive_values(
            item["restricted_mean_trip_time_seconds"]["d0_minus_n0"]
            for item in values
        ),
        "queue_burden_relative_change": descriptive_values(queue_changes),
        "n0_completion_fraction": descriptive_values(
            item["completion_fraction"]["n0"] for item in values
        ),
        "d0_completion_fraction": descriptive_values(
            item["completion_fraction"]["d0"] for item in values
        ),
        "calibration_observations_only": True,
        "hypothesis_significance_test_performed": False,
    }


def evaluate_seed_pair(
    label: str,
    multiplier: int,
    seed: int,
    n0_dir: Path,
    d0_dir: Path,
    n0_metrics: Mapping[str, Any],
    d0_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    route_path, manifest_path = demand_paths(label, seed)
    demand = json.loads(manifest_path.read_text(encoding="utf-8"))
    n0_summary = json.loads((n0_dir / "exposure-summary.json").read_text())
    d0_summary = json.loads((d0_dir / "exposure-summary.json").read_text())
    n0_events = json.loads((n0_dir / "exposure-events.json").read_text())["events"]
    d0_events = json.loads((d0_dir / "exposure-events.json").read_text())["events"]
    n0_ledger = json.loads((n0_dir / "vehicle-ledger.json").read_text())
    d0_ledger = json.loads((d0_dir / "vehicle-ledger.json").read_text())
    lane = d0_summary["lane_visit_diagnostics"][RESTRICTED_LANE]
    n0_observer_lifecycle = exact_observer_permission_lifecycle(
        n0_events, disrupted=False
    )
    d0_observer_lifecycle = exact_observer_permission_lifecycle(
        d0_events, disrupted=True
    )
    n0_raw_lifecycle = exact_raw_disruption_lifecycle(n0_dir, disrupted=False)
    d0_raw_lifecycle = exact_raw_disruption_lifecycle(d0_dir, disrupted=True)
    local = paired_local_response(n0_dir, d0_dir)
    recovery = recovery_diagnostic(
        n0_dir,
        d0_dir,
        Path("selection")
        / label.lower()
        / f"seed-{seed}-recovery-excess-queue.csv",
    )
    scheduled = int(n0_metrics["scheduled_trips"])
    if scheduled != 180 * multiplier or int(d0_metrics["scheduled_trips"]) != scheduled:
        raise AssertionError("run metrics population differs from candidate")
    n0_queue_exact = exact_fraction(n0_metrics["cumulative_queue_vehicle_seconds"])
    d0_queue_exact = exact_fraction(d0_metrics["cumulative_queue_vehicle_seconds"])
    queue_relative_exact = (
        None
        if n0_queue_exact == 0
        else (d0_queue_exact - n0_queue_exact) / n0_queue_exact
    )
    n0_restricted_total = sum(
        (exact_fraction(item["restricted_trip_time_seconds"]) for item in n0_ledger.values()),
        Fraction(0, 1),
    )
    d0_restricted_total = sum(
        (exact_fraction(item["restricted_trip_time_seconds"]) for item in d0_ledger.values()),
        Fraction(0, 1),
    )
    mean_difference_exact = (d0_restricted_total - n0_restricted_total) / scheduled
    n0_trace = trace_integrity(n0_dir, n0_metrics, disrupted=False)
    d0_trace = trace_integrity(d0_dir, d0_metrics, disrupted=True)
    n0_command = command_preserves_calibration_boundary(n0_dir, route_path)
    d0_command = command_preserves_calibration_boundary(d0_dir, route_path)
    n0_vehroute = vehroute_matches_manifest(
        n0_dir / "vehroute.xml", demand, int(n0_metrics["departed_trips"])
    )
    d0_vehroute = vehroute_matches_manifest(
        d0_dir / "vehroute.xml", demand, int(d0_metrics["departed_trips"])
    )
    n0_ledger_integrity = ledger_matches_manifest_and_metrics(
        n0_ledger, demand, n0_metrics
    )
    d0_ledger_integrity = ledger_matches_manifest_and_metrics(
        d0_ledger, demand, d0_metrics
    )
    route_hash = sha256(route_path)
    manifest_hash = sha256(manifest_path)
    n0_execution = json.loads((n0_dir / "execution-receipt.json").read_text())
    d0_execution = json.loads((d0_dir / "execution-receipt.json").read_text())
    n0_input_hashes = n0_execution["input_sha256"]
    d0_input_hashes = d0_execution["input_sha256"]
    allowed_teleport_integrity_error = (
        "teleport events present despite disabled teleport policy"
    )
    n0_core_integrity_errors = sorted(
        error
        for error in n0_metrics["integrity_errors"]
        if error != allowed_teleport_integrity_error
    )
    d0_core_integrity_errors = sorted(
        error
        for error in d0_metrics["integrity_errors"]
        if error != allowed_teleport_integrity_error
    )
    static_noninterference = json.loads(
        (ATTEMPT_CHECKS / "static-noninterference.json").read_text()
    )
    integrity_checks = {
        "n0_no_nonteleport_base_integrity_errors": not n0_core_integrity_errors,
        "d0_no_nonteleport_base_integrity_errors": not d0_core_integrity_errors,
        "n0_zero_collisions": int(n0_metrics["collision_count"]) == 0,
        "d0_zero_collisions": int(d0_metrics["collision_count"]) == 0,
        "n0_collision_artifact_present_valid_and_empty": empty_collision_artifact_is_valid(
            n0_dir / "collisions.xml"
        ),
        "d0_collision_artifact_present_valid_and_empty": empty_collision_artifact_is_valid(
            d0_dir / "collisions.xml"
        ),
        "n0_zero_invalid_failed_routes": int(n0_metrics["failed_invalid_trips"]) == 0,
        "d0_zero_invalid_failed_routes": int(d0_metrics["failed_invalid_trips"]) == 0,
        "n0_zero_unexplained_simulator_errors": not (
            n0_dir / "simulator-errors.log"
        ).read_text(encoding="utf-8").strip(),
        "d0_zero_unexplained_simulator_errors": not (
            d0_dir / "simulator-errors.log"
        ).read_text(encoding="utf-8").strip(),
        "restricted_lane_post_activation_entries_zero": int(
            lane["post_activation_entry_count"]
        )
        == 0,
        "n0_observer_permission_lifecycle_exact": n0_observer_lifecycle["pass"],
        "d0_observer_permission_lifecycle_exact": d0_observer_lifecycle["pass"],
        "n0_raw_disruption_lifecycle_exact": n0_raw_lifecycle["pass"],
        "d0_raw_disruption_lifecycle_exact": d0_raw_lifecycle["pass"],
        "n0_all_scheduled_accounted": bool(n0_metrics["trip_accounting_reconciled"]),
        "d0_all_scheduled_accounted": bool(d0_metrics["trip_accounting_reconciled"]),
        "n0_ledger_reconciles_manifest_and_metrics": n0_ledger_integrity["pass"],
        "d0_ledger_reconciles_manifest_and_metrics": d0_ledger_integrity["pass"],
        "n0_accounting_cardinality_exact": int(n0_metrics["arrived_trips"])
        + int(n0_metrics["unfinished_trips"])
        == scheduled,
        "d0_accounting_cardinality_exact": int(d0_metrics["arrived_trips"])
        + int(d0_metrics["unfinished_trips"])
        == scheduled,
        "all_metrics_and_observations_finite": all(
            numeric_values_are_finite(value)
            for value in (
                n0_metrics,
                d0_metrics,
                n0_summary,
                d0_summary,
                n0_ledger,
                d0_ledger,
                local,
                recovery,
            )
        ),
        "n0_time_configuration_exact": (
            exact_fraction(n0_metrics["simulation_end_seconds"]) == H_PILOT
            and exact_fraction(n0_metrics["h_pilot_seconds"]) == H_PILOT
            and exact_fraction(n0_metrics["simulation_step_seconds"]) == 1
        ),
        "d0_time_configuration_exact": (
            exact_fraction(d0_metrics["simulation_end_seconds"]) == H_PILOT
            and exact_fraction(d0_metrics["h_pilot_seconds"]) == H_PILOT
            and exact_fraction(d0_metrics["simulation_step_seconds"]) == 1
        ),
        "n0_fixed_tls_unchanged": bool(n0_metrics["fixed_time_programs_unchanged"]),
        "d0_fixed_tls_unchanged": bool(d0_metrics["fixed_time_programs_unchanged"]),
        "n0_all_nine_tls_cycled": (
            len(n0_metrics["traffic_light_state_transition_counts"]) == 9
            and all(
                int(value) > 0
                for value in n0_metrics["traffic_light_state_transition_counts"].values()
            )
        ),
        "d0_all_nine_tls_cycled": (
            len(d0_metrics["traffic_light_state_transition_counts"]) == 9
            and all(
                int(value) > 0
                for value in d0_metrics["traffic_light_state_transition_counts"].values()
            )
        ),
        "n0_routes_unchanged": bool(n0_metrics["routes_unchanged"]),
        "d0_routes_unchanged": bool(d0_metrics["routes_unchanged"]),
        "n0_final_vehroutes_match_manifest": n0_vehroute["pass"],
        "d0_final_vehroutes_match_manifest": d0_vehroute["pass"],
        "n0_command_preserves_boundary": n0_command["pass"],
        "d0_command_preserves_boundary": d0_command["pass"],
        "same_frozen_route_hash_for_pair": (
            demand["route_file_sha256"] == route_hash
            and n0_input_hashes.get(route_path.as_posix()) == route_hash
            and d0_input_hashes.get(route_path.as_posix()) == route_hash
            and n0_input_hashes == d0_input_hashes
        ),
        "manifest_hash_stable_for_pair": (
            n0_input_hashes.get(manifest_path.as_posix()) == manifest_hash
            and d0_input_hashes.get(manifest_path.as_posix()) == manifest_hash
        ),
        "no_rerouting_evidenced": (
            demand["dynamic_rerouting"] is False
            and static_noninterference["status"] == "PASS"
            and n0_command["pass"]
            and d0_command["pass"]
            and n0_vehroute["pass"]
            and d0_vehroute["pass"]
        ),
        "n0_exposure_observability_complete": bool(
            n0_summary["exposure_observability_complete"]
        ),
        "d0_exposure_observability_complete": bool(
            d0_summary["exposure_observability_complete"]
        ),
        "observer_identity_exact": (
            n0_summary["observer_identity"] == OBSERVER_IDENTITY
            and d0_summary["observer_identity"] == OBSERVER_IDENTITY
        ),
        "n0_trace_integrity": n0_trace["pass"],
        "d0_trace_integrity": d0_trace["pass"],
        "n0_native_waiting_coverage_complete": bool(
            n0_metrics["sumo_waiting_time_coverage_departed_trips"]
        ),
        "d0_native_waiting_coverage_complete": bool(
            d0_metrics["sumo_waiting_time_coverage_departed_trips"]
        ),
        "scenario_seed_labels_exact": (
            int(n0_metrics["scenario_seed"]) == seed
            and int(d0_metrics["scenario_seed"]) == seed
        ),
        "condition_labels_exact": (
            n0_metrics["condition_label"] == "NORMAL"
            and d0_metrics["condition_label"] == "DISRUPTED"
            and n0_metrics["disruption_expected"] is False
            and d0_metrics["disruption_expected"] is True
        ),
        "n0_has_no_disruption_lifecycle_flags": (
            n0_metrics["disruption_application_validated"] is None
            and n0_metrics["permission_restoration_confirmed"] is None
        ),
        "disruption_application_validated": d0_metrics[
            "disruption_application_validated"
        ]
        is True,
        "permission_restoration_confirmed": d0_metrics[
            "permission_restoration_confirmed"
        ]
        is True,
    }
    observation = {
        "integrity_pass": all(integrity_checks.values()),
        "n0_completion_fraction": Fraction(int(n0_metrics["arrived_trips"]), scheduled),
        "d0_completion_fraction": Fraction(int(d0_metrics["arrived_trips"]), scheduled),
        "n0_teleport_events": sum(
            int(n0_metrics[key])
            for key in (
                "teleport_start_events",
                "teleport_end_events",
                "teleported_terminal_trips",
            )
        ),
        "d0_teleport_events": sum(
            int(d0_metrics[key])
            for key in (
                "teleport_start_events",
                "teleport_end_events",
                "teleported_terminal_trips",
            )
        ),
        "d0_exposure_count": int(d0_summary["unique_edge_entry_counts"]["during"]),
        "mean_trip_time_difference_seconds": mean_difference_exact,
        "queue_burden_relative_change": queue_relative_exact,
        "local_physical_response_observed": local[
            "local_physical_response_observed"
        ],
    }
    qualification = qualification_from_observations(observation)

    def run_evidence_binding(run_dir: Path, metrics: Mapping[str, Any]) -> dict[str, Any]:
        bound_files = (
            "final-metrics.json",
            "vehicle-ledger.json",
            "step-trace.csv",
            "exposure-events.json",
            "exposure-summary.json",
            "disruption-events.json",
            "execution-receipt.json",
            "observer-execution-receipt.json",
            "calibration-run-binding.json",
        )
        return {
            "identity": run_dir.as_posix(),
            "artifact_sha256": {
                name: sha256(run_dir / name) for name in bound_files
            },
            "simulation_wall_clock_runtime_seconds": metrics[
                "simulation_wall_clock_runtime_seconds"
            ],
        }

    return {
        "candidate": label,
        "multiplier": multiplier,
        "seed": seed,
        "scheduled": scheduled,
        "arrived": {
            "n0": int(n0_metrics["arrived_trips"]),
            "d0": int(d0_metrics["arrived_trips"]),
        },
        "unfinished": {
            "n0": int(n0_metrics["unfinished_trips"]),
            "d0": int(d0_metrics["unfinished_trips"]),
        },
        "completion_fraction": {
            "n0": float(observation["n0_completion_fraction"]),
            "d0": float(observation["d0_completion_fraction"]),
            "n0_exact": f"{int(n0_metrics['arrived_trips'])}/{scheduled}",
            "d0_exact": f"{int(d0_metrics['arrived_trips'])}/{scheduled}",
        },
        "exposure": {
            "d0_unique_A1B1_entries_during_event": observation[
                "d0_exposure_count"
            ],
            "vehicle_ids": local["exposed_vehicle_ids"],
            "restricted_lane_preexisting_occupant_count": lane[
                "preexisting_occupant_count"
            ],
            "restricted_lane_post_activation_entry_count": lane[
                "post_activation_entry_count"
            ],
            "restricted_lane_post_activation_entry_ids": lane[
                "post_activation_entry_ids"
            ],
            "surviving_lane_event_unique_user_count": d0_summary[
                "lane_visit_diagnostics"
            ][SURVIVING_LANE]["event_unique_user_count"],
        },
        "restricted_mean_trip_time_seconds": {
            "n0": n0_metrics["restricted_mean_trip_time_seconds"],
            "d0": d0_metrics["restricted_mean_trip_time_seconds"],
            "d0_minus_n0": float(mean_difference_exact),
            "exact_total_difference_seconds": float(
                d0_restricted_total - n0_restricted_total
            ),
            "exact_gate_right_hand_side_seconds": scheduled,
        },
        "restricted_p95_trip_time_seconds_nearest_rank": {
            "n0": n0_metrics["restricted_p95_trip_time_seconds_nearest_rank"],
            "d0": d0_metrics["restricted_p95_trip_time_seconds_nearest_rank"],
        },
        "queue_burden_vehicle_seconds": {
            "n0": float(n0_queue_exact),
            "d0": float(d0_queue_exact),
            "d0_minus_n0": float(d0_queue_exact - n0_queue_exact),
            "relative_change": (
                None if queue_relative_exact is None else float(queue_relative_exact)
            ),
            "exact_gate_left_100_times_d0": float(100 * d0_queue_exact),
            "exact_gate_right_105_times_n0": float(105 * n0_queue_exact),
        },
        "native_waiting_time_seconds": {
            "n0_total": n0_metrics["sumo_tripinfo_waiting_time_seconds_total"],
            "d0_total": d0_metrics["sumo_tripinfo_waiting_time_seconds_total"],
            "n0_mean": n0_metrics[
                "sumo_tripinfo_waiting_time_seconds_mean_all_scheduled"
            ],
            "d0_mean": d0_metrics[
                "sumo_tripinfo_waiting_time_seconds_mean_all_scheduled"
            ],
        },
        "throughput_non_teleported_trips": {
            "n0": n0_metrics["non_teleported_throughput_trips"],
            "d0": d0_metrics["non_teleported_throughput_trips"],
        },
        "teleport_events": {
            "n0_start": n0_metrics["teleport_start_events"],
            "n0_end": n0_metrics["teleport_end_events"],
            "n0_terminal": n0_metrics["teleported_terminal_trips"],
            "d0_start": d0_metrics["teleport_start_events"],
            "d0_end": d0_metrics["teleport_end_events"],
            "d0_terminal": d0_metrics["teleported_terminal_trips"],
        },
        "collisions": {
            "n0": n0_metrics["collision_count"],
            "d0": d0_metrics["collision_count"],
        },
        "local_physical_response": local,
        "recovery_diagnostic": recovery,
        "lifecycle_evidence": {
            "n0_observer": n0_observer_lifecycle,
            "d0_observer": d0_observer_lifecycle,
            "n0_raw": n0_raw_lifecycle,
            "d0_raw": d0_raw_lifecycle,
        },
        "trace_integrity": {"n0": n0_trace, "d0": d0_trace},
        "ledger_integrity": {
            "n0": n0_ledger_integrity,
            "d0": d0_ledger_integrity,
        },
        "route_and_no_rerouting_evidence": {
            "route_file_identity": route_path.as_posix(),
            "route_file_sha256": route_hash,
            "manifest_identity": manifest_path.as_posix(),
            "manifest_sha256": manifest_hash,
            "n0_command": n0_command,
            "d0_command": d0_command,
            "n0_vehroute": n0_vehroute,
            "d0_vehroute": d0_vehroute,
        },
        "base_integrity_errors": {
            "n0_all": n0_metrics["integrity_errors"],
            "d0_all": d0_metrics["integrity_errors"],
            "n0_nonteleport": n0_core_integrity_errors,
            "d0_nonteleport": d0_core_integrity_errors,
        },
        "run_evidence": {
            "n0": run_evidence_binding(n0_dir, n0_metrics),
            "d0": run_evidence_binding(d0_dir, d0_metrics),
        },
        "integrity_checks": integrity_checks,
        "integrity_pass": observation["integrity_pass"],
        "qualification": qualification,
    }


def normalized_json(path: Path, omitted_keys: set[str]) -> Any:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in omitted_keys:
            payload.pop(key, None)
    return payload


def canonical_xml_children(path: Path, tag: str) -> dict[str, Any]:
    def canonical(node: ET.Element) -> Any:
        return {
            "tag": node.tag,
            "attributes": dict(sorted(node.attrib.items())),
            "children": [canonical(child) for child in list(node)],
        }

    nodes = ET.parse(path).getroot().findall(tag)
    identifiers = [node.attrib["id"] for node in nodes]
    if len(identifiers) != len(set(identifiers)):
        raise CalibrationIntegrityFailure(
            f"duplicate {tag} identifiers in deterministic comparison"
        )
    return {node.attrib["id"]: canonical(node) for node in nodes}


def executed_route_binding(run_dir: Path) -> dict[str, Any]:
    receipt = json.loads((run_dir / "execution-receipt.json").read_text())
    route_identity = command_option(receipt["command"], "--route-files")
    if route_identity is None:
        return {"identity": None, "sha256": None, "receipt_matches_disk": False}
    frozen_hash = receipt["input_sha256"].get(route_identity)
    return {
        "identity": route_identity,
        "sha256": frozen_hash,
        "receipt_matches_disk": (
            frozen_hash is not None
            and Path(route_identity).is_file()
            and sha256(Path(route_identity)) == frozen_hash
        ),
    }


def deterministic_repeat_comparison(
    original_dir: Path, repeat_dir: Path, disrupted: bool
) -> dict[str, Any]:
    original_metrics = json.loads((original_dir / "final-metrics.json").read_text())
    repeat_metrics = json.loads((repeat_dir / "final-metrics.json").read_text())
    original_exposure = json.loads((original_dir / "exposure-summary.json").read_text())
    repeat_exposure = json.loads((repeat_dir / "exposure-summary.json").read_text())
    original_events = json.loads((original_dir / "exposure-events.json").read_text())
    repeat_events = json.loads((repeat_dir / "exposure-events.json").read_text())
    original_exposure.pop("run_id", None)
    repeat_exposure.pop("run_id", None)
    original_events.pop("run_id", None)
    repeat_events.pop("run_id", None)
    original_route_binding = executed_route_binding(original_dir)
    repeat_route_binding = executed_route_binding(repeat_dir)
    checks = {
        "scientific_metrics_equal": BASE.scientific_metrics_projection(
            original_metrics
        )
        == BASE.scientific_metrics_projection(repeat_metrics),
        "queue_trace_byte_equal": (original_dir / "step-trace.csv").read_bytes()
        == (repeat_dir / "step-trace.csv").read_bytes(),
        "vehicle_ledger_equal": json.loads(
            (original_dir / "vehicle-ledger.json").read_text()
        )
        == json.loads((repeat_dir / "vehicle-ledger.json").read_text()),
        "tripinfo_semantically_equal": canonical_xml_children(
            original_dir / "tripinfo.xml", "tripinfo"
        )
        == canonical_xml_children(repeat_dir / "tripinfo.xml", "tripinfo"),
        "vehroute_semantically_equal": canonical_xml_children(
            original_dir / "vehroute.xml", "vehicle"
        )
        == canonical_xml_children(repeat_dir / "vehroute.xml", "vehicle"),
        "normalized_exposure_summary_equal": original_exposure == repeat_exposure,
        "normalized_exposure_events_equal": original_events == repeat_events,
        "pre_event_occupancy_equal": json.loads(
            (original_dir / "pre-event-occupancy.json").read_text()
        )
        == json.loads((repeat_dir / "pre-event-occupancy.json").read_text()),
        "event_lifecycle_equal": json.loads(
            (original_dir / "disruption-events.json").read_text()
        )
        == json.loads((repeat_dir / "disruption-events.json").read_text()),
        "lane_compliance_equal": original_exposure["lane_visit_diagnostics"]
        [RESTRICTED_LANE]["post_activation_entry_count"]
        == repeat_exposure["lane_visit_diagnostics"][RESTRICTED_LANE][
            "post_activation_entry_count"
        ],
        "route_file_binding_equal": (
            original_route_binding == repeat_route_binding
            and original_route_binding["receipt_matches_disk"] is True
        ),
    }
    if disrupted:
        checks["disrupted_lifecycle_complete"] = (
            repeat_metrics["disruption_application_validated"] is True
            and repeat_metrics["permission_restoration_confirmed"] is True
        )
    return {
        "pass": all(checks.values()),
        "checks": checks,
        "route_file_binding": original_route_binding,
    }


def candidate_run_dir(label: str, seed: int, condition: str) -> Path:
    return (
        Path("runs")
        / label.lower()
        / f"seed-{seed}"
        / condition.lower()
        / f"attempt-{RUN_ATTEMPT:03d}"
    )


def verify_pristine_execution_targets() -> None:
    targets = [Path("runs"), ATTEMPT_CHECKS, Path("selection"), Path("freeze")]
    existing = sorted(path.as_posix() for path in targets if path.exists())
    if existing:
        raise AssertionError(f"calibration execution targets are not pristine: {existing}")
    forbidden_existing_inputs = [NETWORK_PATH, OBSERVER_PATH, DISRUPTION_PATH, Path("inputs/demand")]
    existing_inputs = sorted(
        path.as_posix() for path in forbidden_existing_inputs if path.exists()
    )
    if existing_inputs:
        raise AssertionError(f"calibration frozen inputs already exist: {existing_inputs}")


def create_inventory() -> dict[str, Any]:
    inventory_path = ATTEMPT_CHECKS / "evidence-inventory.json"
    hash_path = ATTEMPT_CHECKS / "artifact-sha256.json"
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
            "calibration_identity": CALIBRATION_IDENTITY,
            "artifact_count_total_including_hash_manifest": len(artifacts),
            "artifacts": artifacts,
            "hash_manifest_self_hash_included": False,
        },
    )
    paths_to_hash = sorted(
        path
        for path in Path(".").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path != hash_path
    )
    hashes = {path.as_posix(): sha256(path) for path in paths_to_hash}
    write_json_once(
        hash_path,
        {"sha256": dict(sorted(hashes.items())), "self_hash_included": False},
    )
    mismatches = [
        identity
        for identity, expected in hashes.items()
        if sha256(Path(identity)) != expected
    ]
    if mismatches:
        raise AssertionError(f"calibration evidence hash mismatch: {mismatches}")
    return {
        "artifact_count": len(artifacts),
        "hashed_artifact_count": len(hashes),
        "hash_mismatch_count": 0,
    }


def environment_receipt() -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["sumo", "--version"], check=True, capture_output=True, text=True
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise CalibrationBlocked("SUMO version preflight is unavailable") from error
    return {
        "python_version": sys.version.split()[0],
        "sumo_version_line": (result.stdout or result.stderr).splitlines()[0],
        "sumo_version_output": (result.stdout or result.stderr).splitlines(),
        "traci_module_identity": str(getattr(BASE.traci, "__file__", "UNKNOWN")),
        "operating_system": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "UNREPORTED_BY_PLATFORM",
        "logical_cpu_count": os.cpu_count(),
        "hardware_accelerator_used": False,
        "simulation_executed_by_version_check": False,
    }


def physical_disruption_specification() -> dict[str, Any]:
    source = json.loads(ORIGINAL_DISRUPTION_PATH.read_text(encoding="utf-8"))
    physical_keys = (
        "disruption_family",
        "implementation",
        "selection_basis",
        "directed_edge_id",
        "lane_id",
        "original_lane_count",
        "remaining_route_feasible_lane_id",
        "remaining_lane_successor_for_exposed_route",
        "vehicle_class_temporarily_disallowed",
        "start_step_inclusive",
        "end_step_exclusive",
        "full_link_closure",
        "rerouting_permitted",
        "exact_capacity_percentage_claimed",
    )
    physical = {key: source[key] for key in physical_keys}
    expected = {
        "directed_edge_id": MONITORED_EDGE,
        "lane_id": RESTRICTED_LANE,
        "remaining_route_feasible_lane_id": SURVIVING_LANE,
        "vehicle_class_temporarily_disallowed": PASSENGER_CLASS,
        "start_step_inclusive": DISRUPTION_START,
        "end_step_exclusive": DISRUPTION_END,
        "full_link_closure": False,
        "rerouting_permitted": False,
        "exact_capacity_percentage_claimed": False,
    }
    if any(physical.get(key) != value for key, value in expected.items()):
        raise AssertionError("physical disruption source differs from frozen event")
    return {
        "physical_event": physical,
        "source_sha256": EXPECTED_ORIGINAL_DISRUPTION_SHA256,
        "source_contains_original_1x_demand_metadata": True,
        "source_1x_demand_fields_are_not_calibrated_candidate_counts": True,
    }


def main() -> None:
    global ATTEMPT_INITIALIZED
    if Path.cwd().resolve() != BUNDLE_ROOT:
        raise AssertionError("calibration runner must start in its bundle root")
    verify_pristine_execution_targets()
    contract = validate_contract()
    repository_before = repository_state()
    original_before = tree_snapshot(ORIGINAL_ROOT)
    diagnostic_before = tree_snapshot(DIAGNOSTIC_ROOT)
    if (
        len(original_before) != EXPECTED_ORIGINAL_TREE_OBJECT_COUNT
        or snapshot_digest(original_before) != EXPECTED_ORIGINAL_TREE_DIGEST
    ):
        raise AssertionError("original B0 evidence identity differs from frozen record")
    if (
        len(diagnostic_before) != EXPECTED_DIAGNOSTIC_TREE_OBJECT_COUNT
        or snapshot_digest(diagnostic_before) != EXPECTED_DIAGNOSTIC_TREE_DIGEST
    ):
        raise AssertionError("validated diagnostic evidence identity differs from record")

    ATTEMPT_CHECKS.mkdir(parents=True)
    ATTEMPT_INITIALIZED = True
    write_json_once(ATTEMPT_CHECKS / "repository-state-before.json", repository_before)
    write_json_once(
        ATTEMPT_CHECKS / "source-evidence-state-before.json",
        {
            "original_b0_object_count": len(original_before),
            "original_b0_tree_digest": snapshot_digest(original_before),
            "diagnostic_object_count": len(diagnostic_before),
            "diagnostic_tree_digest": snapshot_digest(diagnostic_before),
        },
    )
    input_freeze = prepare_frozen_inputs()
    write_json_once(
        ATTEMPT_CHECKS / "static-noninterference.json",
        static_noninterference_receipt(),
    )
    write_json_once(
        ATTEMPT_CHECKS / "pre-execution-tests.json", run_preflight_tests()
    )
    verify_all_frozen_input_hashes()
    write_json_once(ATTEMPT_CHECKS / "environment.json", environment_receipt())
    write_bytes_once(
        ATTEMPT_CHECKS / "run_calibration.executed.py", RUNNER_PATH.read_bytes()
    )
    runner_hash = FROZEN_INPUT_HASHES[RUNNER_PATH.as_posix()]
    write_json_once(
        ATTEMPT_CHECKS / "execution-source-sha256.json",
        {
            "runner_sha256": runner_hash,
            "observer_sha256": sha256(OBSERVER_PATH),
            "contract_sha256": sha256(CONTRACT_PATH),
            "baseline_runner_derivation": BASE_DERIVATION_RECEIPT,
        },
    )
    observer_module = load_module_from_source(
        OBSERVER_PATH, "frozen_calibration_exposure_observer"
    )
    if observer_module.OBSERVER_IDENTITY != OBSERVER_IDENTITY:
        raise AssertionError("observer identity mismatch")

    candidate_results: dict[str, Any] = {}
    selected_label: str | None = None
    selected_multiplier: int | None = None
    executed_levels: list[str] = []
    terminal_status: str | None = None
    for label, multiplier in DEMAND_LADDER:
        executed_levels.append(label)
        seed_results: dict[str, Any] = {}
        for seed in CALIBRATION_SEEDS:
            route_path, manifest_path = demand_paths(label, seed)
            demand = json.loads(manifest_path.read_text(encoding="utf-8"))
            n0_dir = candidate_run_dir(label, seed, "n0-cal")
            d0_dir = candidate_run_dir(label, seed, "d0-cal")
            n0_metrics = run_observed_condition(
                observer_module=observer_module,
                run_id=f"{label}-S{seed}-N0-CAL",
                run_dir=n0_dir,
                disrupted=False,
                seed=seed,
                route_path=route_path,
                manifest_path=manifest_path,
                demand=demand,
                runner_hash=runner_hash,
            )
            d0_metrics = run_observed_condition(
                observer_module=observer_module,
                run_id=f"{label}-S{seed}-D0-CAL",
                run_dir=d0_dir,
                disrupted=True,
                seed=seed,
                route_path=route_path,
                manifest_path=manifest_path,
                demand=demand,
                runner_hash=runner_hash,
            )
            seed_result = evaluate_seed_pair(
                label,
                multiplier,
                seed,
                n0_dir,
                d0_dir,
                n0_metrics,
                d0_metrics,
            )
            seed_results[str(seed)] = seed_result
            write_json_once(
                Path("selection")
                / label.lower()
                / f"seed-{seed}-qualification.json",
                seed_result,
            )
            print(
                json.dumps(
                    {
                        "event": "SEED_PAIR_COMPLETE",
                        "candidate": label,
                        "seed": seed,
                        "qualifies": seed_result["qualification"]["qualifies"],
                        "failed_checks": seed_result["qualification"]["failed_checks"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if seed_result["qualification"]["status"] == "INTEGRITY_FAILURE":
                terminal_status = "FAIL"
                break
        candidate_status = aggregate_seed_qualification_statuses(
            item["qualification"]["status"] for item in seed_results.values()
        )
        candidate_result = {
            "candidate": label,
            "multiplier": multiplier,
            "scheduled_trips": 180 * multiplier,
            "candidate_status": candidate_status,
            "all_three_seeds_executed": len(seed_results) == len(CALIBRATION_SEEDS),
            "all_three_seeds_qualify": candidate_status == "QUALIFIES",
            "seed_results": seed_results,
            "descriptive_across_seed_summary": candidate_descriptive_summary(
                seed_results
            ),
        }
        candidate_results[label] = candidate_result
        write_json_once(
            Path("selection") / label.lower() / "candidate-decision.json",
            candidate_result,
        )
        print(
            json.dumps(
                {
                    "event": "CANDIDATE_COMPLETE",
                    "candidate": label,
                    "candidate_status": candidate_status,
                    "all_three_seeds_qualify": candidate_status == "QUALIFIES",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        if candidate_status == "INTEGRITY_FAILURE":
            terminal_status = "FAIL"
            break
        if candidate_status == "NOT_IDENTIFIABLE":
            terminal_status = "INCONCLUSIVE"
            break
        if candidate_status == "QUALIFIES":
            selected_label = label
            selected_multiplier = multiplier
            break

    not_run_levels = [
        label for label, _ in DEMAND_LADDER if label not in executed_levels
    ]
    repeat_result: dict[str, Any] | None = None
    determinism_status = "NOT_APPLICABLE"
    if (
        terminal_status is None
        and selected_label is not None
        and selected_multiplier is not None
    ):
        seed = CALIBRATION_SEEDS[0]
        route_path, manifest_path = demand_paths(selected_label, seed)
        demand = json.loads(manifest_path.read_text(encoding="utf-8"))
        n0_original = candidate_run_dir(selected_label, seed, "n0-cal")
        d0_original = candidate_run_dir(selected_label, seed, "d0-cal")
        n0_repeat = candidate_run_dir(selected_label, seed, "n0-cal-r")
        d0_repeat = candidate_run_dir(selected_label, seed, "d0-cal-r")
        run_observed_condition(
            observer_module=observer_module,
            run_id=f"{selected_label}-S{seed}-N0-CAL-R",
            run_dir=n0_repeat,
            disrupted=False,
            seed=seed,
            route_path=route_path,
            manifest_path=manifest_path,
            demand=demand,
            runner_hash=runner_hash,
        )
        run_observed_condition(
            observer_module=observer_module,
            run_id=f"{selected_label}-S{seed}-D0-CAL-R",
            run_dir=d0_repeat,
            disrupted=True,
            seed=seed,
            route_path=route_path,
            manifest_path=manifest_path,
            demand=demand,
            runner_hash=runner_hash,
        )
        repeat_result = {
            "seed": seed,
            "candidate": selected_label,
            "run_evidence_identities": {
                "n0_original": n0_original.as_posix(),
                "n0_repeat": n0_repeat.as_posix(),
                "d0_original": d0_original.as_posix(),
                "d0_repeat": d0_repeat.as_posix(),
            },
            "n0": deterministic_repeat_comparison(
                n0_original, n0_repeat, disrupted=False
            ),
            "d0": deterministic_repeat_comparison(
                d0_original, d0_repeat, disrupted=True
            ),
        }
        repeat_result["pass"] = repeat_result["n0"]["pass"] and repeat_result[
            "d0"
        ]["pass"]
        determinism_status = "YES" if repeat_result["pass"] else "NO"
        write_json_once(
            Path("selection") / "selected-deterministic-repeat.json", repeat_result
        )

    selection = {
        "selection_rule": "FIRST_QUALIFYING",
        "selected_calibrated_demand_level": selected_label or "NONE",
        "selected_multiplier": selected_multiplier,
        "executed_levels": executed_levels,
        "not_run_due_to_first_qualifying_stop": not_run_levels,
        "candidate_results": candidate_results,
        "selected_scenario_determinism_pass": determinism_status,
        "repeat_result": repeat_result,
    }
    write_json_once(Path("selection/first-qualifying-selection.json"), selection)

    calibrated_scenario_frozen = False
    freeze: dict[str, Any] | None = None
    if (
        terminal_status is None
        and selected_label is not None
        and determinism_status == "YES"
    ):
        selected_route_files = {
            str(seed): {
                "identity": demand_paths(selected_label, seed)[0].as_posix(),
                "sha256": sha256(demand_paths(selected_label, seed)[0]),
                "manifest_identity": demand_paths(selected_label, seed)[1].as_posix(),
                "manifest_sha256": sha256(demand_paths(selected_label, seed)[1]),
            }
            for seed in CALIBRATION_SEEDS
        }
        freeze = {
            "status": "PROPOSED_PENDING_FINAL_IMMUTABILITY_AND_READBACK",
            "scenario_identity": CALIBRATED_SCENARIO_IDENTITY,
            "frozen_at_utc": utc_now(),
            "network_identity": "B0_GRID_3X3_V1",
            "network_sha256": sha256(NETWORK_PATH),
            "demand_generation_algorithm": contract["demand_generation"],
            "calibration_runner_sha256": runner_hash,
            "derived_baseline_runner": BASE_DERIVATION_RECEIPT,
            "calibration_contract_sha256": sha256(CONTRACT_PATH),
            "selected_demand_level": selected_label,
            "selected_multiplier": selected_multiplier,
            "calibration_seeds": list(CALIBRATION_SEEDS),
            "selected_route_files": selected_route_files,
            "scientific_configuration": contract["scientific_configuration"],
            "research_boundary": contract["research_boundary"],
            "calibration_seed_usage_boundary": (
                "CALIBRATION_ONLY; EXCLUDED_FROM_FINAL_CONFIRMATORY_TREATMENT_"
                "ESTIMATE_UNLESS_LATER_PREREGISTERED"
            ),
            "disruption_specification": physical_disruption_specification(),
            "disruption_specification_sha256": sha256(DISRUPTION_PATH),
            "fixed_tls_identity": {
                "network_embedded_program_id": "0",
                "program_cycle_seconds": 68,
                "unchanged_in_all_runs": True,
            },
            "h_pilot_seconds": H_PILOT,
            "metric_definitions": {
                "primary": "MEAN_RESTRICTED_TRIP_TIME_FROM_SCHEDULED_DEPARTURE_ACROSS_ALL_SCHEDULED_TRIPS",
                "queue": "SUM_OVER_ONE_SECOND_STEPS_OF_NETWORK_WIDE_ACTIVE_PASSENGER_VEHICLES_WITH_SPEED_BELOW_0.1_METRES_PER_SECOND",
                "p95": "NEAREST_RANK_CEILING_0.95_TIMES_N",
            },
            "exposure_observer_identity": OBSERVER_IDENTITY,
            "exposure_observer_sha256": sha256(OBSERVER_PATH),
            "qualification_contract": contract["qualification_contract"],
            "selection_rule": contract["selection_rule"],
            "calibration_location": contract["calibration_location"],
            "all_executed_candidate_results": candidate_results,
            "failed_lower_intensity_candidates": [
                candidate_results[label]
                for label in executed_levels
                if label != selected_label
            ],
            "selected_deterministic_repeat_evidence": repeat_result,
            "effect_threshold_boundary": contract["effect_threshold_boundary"],
            "original_b0_overwritten": False,
        }

    if terminal_status is not None:
        calibration_status = terminal_status
        next_task = (
            "RESOLVE_THE_SINGLE_RECORDED_CALIBRATION_INTEGRITY_CONTRADICTION"
            if terminal_status == "FAIL"
            else "RESOLVE_THE_SINGLE_RECORDED_CALIBRATION_AMBIGUITY"
        )
    elif selected_label is None:
        calibration_status = "NO_QUALIFYING_DEMAND_LEVEL"
        next_task = (
            "BASELINE_ONLY_REVISE_AND_FREEZE_OD_CORRIDOR_CONCENTRATION_AS_THE_"
            "SINGLE_ADDITIONAL_CALIBRATION_AXIS"
        )
    elif determinism_status != "YES":
        calibration_status = "FAIL"
        next_task = (
            "RESOLVE_SELECTED_BASELINE_SCENARIO_DETERMINISM_BEFORE_FREEZING_OR_RL"
        )
    else:
        calibration_status = "PASS"
        next_task = (
            "INDEPENDENTLY_VALIDATE_B0_CALIBRATED_SCENARIO_V1_BEFORE_"
            "PUBLICATION_OR_RL"
        )

    repository_after = repository_state()
    original_after = tree_snapshot(ORIGINAL_ROOT)
    diagnostic_after = tree_snapshot(DIAGNOSTIC_ROOT)
    source_evidence_unchanged = (
        original_before == original_after and diagnostic_before == diagnostic_after
    )
    write_json_once(
        ATTEMPT_CHECKS / "source-evidence-immutability.json",
        {
            "status": "PASS" if source_evidence_unchanged else "FAIL",
            "original_b0_object_count_before": len(original_before),
            "original_b0_object_count_after": len(original_after),
            "original_b0_tree_digest_before": snapshot_digest(original_before),
            "original_b0_tree_digest_after": snapshot_digest(original_after),
            "diagnostic_object_count_before": len(diagnostic_before),
            "diagnostic_object_count_after": len(diagnostic_after),
            "diagnostic_tree_digest_before": snapshot_digest(diagnostic_before),
            "diagnostic_tree_digest_after": snapshot_digest(diagnostic_after),
        },
    )
    if not source_evidence_unchanged:
        raise AssertionError("source B0 or diagnostic evidence changed")
    if repository_after != repository_before:
        raise AssertionError("public repository state changed during calibration")
    write_json_once(ATTEMPT_CHECKS / "repository-state-after.json", repository_after)
    verify_all_frozen_input_hashes()
    if freeze is not None and calibration_status == "PASS":
        freeze["status"] = "FROZEN"
        freeze["final_repository_state_verified"] = True
        freeze["source_evidence_immutability_verified"] = True
        freeze["all_frozen_input_hashes_verified"] = True
        freeze_path = Path("freeze/B0_CALIBRATED_SCENARIO_V1.json")
        write_json_once(freeze_path, freeze)
        freeze_readback = json.loads(freeze_path.read_text(encoding="utf-8"))
        if freeze_readback != freeze or freeze_readback.get("status") != "FROZEN":
            raise CalibrationIntegrityFailure("calibrated scenario freeze readback mismatch")
        write_json_once(
            ATTEMPT_CHECKS / "freeze-readback.json",
            {
                "status": "PASS",
                "scenario_identity": CALIBRATED_SCENARIO_IDENTITY,
                "freeze_sha256": sha256(freeze_path),
                "semantic_readback_equal": True,
            },
        )
        calibrated_scenario_frozen = True
    summary = {
        "calibration_identity": CALIBRATION_IDENTITY,
        "calibration_status": calibration_status,
        "calibration_pretreatment_boundary_preserved": True,
        "A1B1_calibration_location_excluded_from_future_heldout_test": True,
        "calibration_seeds_frozen": True,
        "demand_ladder_predeclared": True,
        "calibration_qualification_contract_frozen": True,
        "selected_calibrated_demand_level": selected_label or "NONE",
        "selected_scenario_determinism_pass": determinism_status,
        "dissertation_effect_threshold_remains_unset": True,
        "calibrated_scenario_frozen": calibrated_scenario_frozen,
        "executed_levels": executed_levels,
        "not_run_levels": not_run_levels,
        "candidate_results": candidate_results,
        "repeat_result": repeat_result,
        "public_git_modified": False,
        "source_evidence_unchanged": True,
        "next_task": next_task,
    }
    write_json_once(ATTEMPT_CHECKS / "bundle-summary.json", summary)
    inventory = create_inventory()
    print(
        json.dumps(
            {
                "event": "CALIBRATION_COMPLETE",
                "status": calibration_status,
                "selected": selected_label or "NONE",
                "inventory": inventory,
            },
            sort_keys=True,
        ),
        flush=True,
    )


def seal_failure(error: BaseException) -> None:
    if not ATTEMPT_INITIALIZED:
        return
    status = (
        "INCONCLUSIVE"
        if isinstance(error, CalibrationInconclusive)
        else "BLOCKED"
        if isinstance(error, CalibrationBlocked)
        else "FAIL"
    )
    seal_errors: list[str] = []
    failure_path = ATTEMPT_CHECKS / "bundle-failure.json"
    try:
        if not failure_path.exists():
            write_json_once(
                failure_path,
                {
                    "status": status,
                    "exception_type": type(error).__name__,
                    "message": str(error),
                    "traceback": traceback.format_exc(),
                    "detected_utc": utc_now(),
                    "scientific_inputs_may_not_be_changed_for_retry": True,
                },
            )
    except BaseException as seal_error:
        seal_errors.append(f"FAILURE_RECEIPT:{type(seal_error).__name__}:{seal_error}")

    immutability: dict[str, Any] = {"status": "NOT_CHECKED"}
    try:
        original = tree_snapshot(ORIGINAL_ROOT)
        diagnostic = tree_snapshot(DIAGNOSTIC_ROOT)
        immutability = {
            "status": "PASS"
            if (
                len(original) == EXPECTED_ORIGINAL_TREE_OBJECT_COUNT
                and snapshot_digest(original) == EXPECTED_ORIGINAL_TREE_DIGEST
                and len(diagnostic) == EXPECTED_DIAGNOSTIC_TREE_OBJECT_COUNT
                and snapshot_digest(diagnostic) == EXPECTED_DIAGNOSTIC_TREE_DIGEST
            )
            else "FAIL",
            "original_b0_object_count": len(original),
            "original_b0_tree_digest": snapshot_digest(original),
            "diagnostic_object_count": len(diagnostic),
            "diagnostic_tree_digest": snapshot_digest(diagnostic),
        }
        path = ATTEMPT_CHECKS / "failure-source-evidence-immutability.json"
        if not path.exists():
            write_json_once(path, immutability)
    except BaseException as seal_error:
        seal_errors.append(f"SOURCE_SNAPSHOT:{type(seal_error).__name__}:{seal_error}")

    repo_after: dict[str, Any] = {"status": "NOT_CHECKED"}
    try:
        repo_after = repository_state()
        repo_after = {"status": "PASS", **repo_after}
        path = ATTEMPT_CHECKS / "failure-repository-state-after.json"
        if not path.exists():
            write_json_once(path, repo_after)
    except BaseException as seal_error:
        repo_after = {
            "status": "FAIL",
            "error": f"{type(seal_error).__name__}:{seal_error}",
        }
        seal_errors.append(f"REPOSITORY_STATE:{type(seal_error).__name__}:{seal_error}")

    input_state: dict[str, Any] = {"status": "NOT_APPLICABLE"}
    if FROZEN_INPUT_HASHES:
        mismatches: dict[str, Any] = {}
        for identity, expected in FROZEN_INPUT_HASHES.items():
            path = Path(identity)
            actual = sha256(path) if path.is_file() else None
            if actual != expected:
                mismatches[identity] = {"expected": expected, "actual": actual}
        input_state = {
            "status": "PASS" if not mismatches else "FAIL",
            "mismatches": mismatches,
        }
        try:
            path = ATTEMPT_CHECKS / "failure-frozen-input-state.json"
            if not path.exists():
                write_json_once(path, input_state)
        except BaseException as seal_error:
            seal_errors.append(f"INPUT_STATE:{type(seal_error).__name__}:{seal_error}")

    try:
        summary_path = ATTEMPT_CHECKS / "bundle-summary.json"
        if not summary_path.exists():
            write_json_once(
                summary_path,
                {
                    "calibration_identity": CALIBRATION_IDENTITY,
                    "calibration_status": status,
                    "selected_calibrated_demand_level": "NONE",
                    "selected_scenario_determinism_pass": "NOT_APPLICABLE",
                    "calibrated_scenario_frozen": False,
                    "dissertation_effect_threshold_remains_unset": True,
                    "public_git_modified": repo_after.get("status") != "PASS",
                    "source_evidence_unchanged": immutability.get("status") == "PASS",
                    "frozen_inputs_unchanged": input_state.get("status")
                    in {"PASS", "NOT_APPLICABLE"},
                    "next_task": (
                        "RESOLVE_THE_RECORDED_CALIBRATION_AMBIGUITY"
                        if status == "INCONCLUSIVE"
                        else "RESTORE_LOCAL_BASELINE_CALIBRATION_EXECUTION_CAPABILITY"
                        if status == "BLOCKED"
                        else "RESOLVE_THE_RECORDED_CALIBRATION_INTEGRITY_FAILURE"
                    ),
                },
            )
    except BaseException as seal_error:
        seal_errors.append(f"FAILURE_SUMMARY:{type(seal_error).__name__}:{seal_error}")

    if seal_errors:
        try:
            path = ATTEMPT_CHECKS / "failure-seal-errors.json"
            if not path.exists():
                write_json_once(path, {"errors": seal_errors})
        except BaseException:
            pass
    try:
        if not (ATTEMPT_CHECKS / "artifact-sha256.json").exists():
            create_inventory()
    except BaseException:
        pass


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        seal_failure(error)
        raise
