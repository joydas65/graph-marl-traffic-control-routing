"""Pure contract tests for the baseline-only demand calibration logic.

These tests intentionally exercise only deterministic in-memory calculations and
temporary trace files.  Importing the calibration module must not start SUMO.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from fractions import Fraction
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "b0" / "calibration" / "run_calibration.py"
BASELINE_RUNNER_PATH = ROOT / "scripts" / "b0" / "run_b0.py"
ARCHIVED_TEST_PATH = (
    ROOT
    / "scripts"
    / "b0"
    / "calibration"
    / "provenance"
    / "calibration_logic_tests_executed.py"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_EXPECTED_SHA256 = {
    RUNNER_PATH: "f44035eac421d428877c356ecfef8c5aa9e0388a820c4b1421997c6346c9c3b4",
    BASELINE_RUNNER_PATH: "d4286193089a8062ae16e51e3dbaf8f26df6be11d43399d6fd998941b275ccab",
    ARCHIVED_TEST_PATH: "1623488c515cdaaf21f9bb6388886437bbc604147421d6e81b67a9406208af63",
}
for _path, _expected_hash in _EXPECTED_SHA256.items():
    if _sha256(_path) != _expected_hash:
        raise RuntimeError(f"published calibration provenance changed: {_path.name}")


def _test_method_asts(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name: ast.dump(node, include_attributes=False)
        for parent in tree.body
        if isinstance(parent, ast.ClassDef)
        for node in parent.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


if _test_method_asts(Path(__file__)) != _test_method_asts(ARCHIVED_TEST_PATH):
    raise RuntimeError("active calibration test methods differ from executed source")

# Loading the exact executed runner normally resolves a historical ignored
# evidence layout and imports TraCI.  Supply only the already-published frozen
# B0 runner bytes and an inert TraCI module while the provenance snapshot is
# imported; neither SUMO nor ignored evidence is opened.
_baseline_runner_bytes = BASELINE_RUNNER_PATH.read_bytes()
_original_read_bytes = Path.read_bytes
_intercept_count = 0


def _read_public_baseline_for_import(path: Path) -> bytes:
    global _intercept_count
    if path.name == "run_b0.py" and path.resolve() != RUNNER_PATH.resolve():
        _intercept_count += 1
        return _baseline_runner_bytes
    return _original_read_bytes(path)


_prior_traci = sys.modules.get("traci")
sys.modules["traci"] = types.ModuleType("traci")
Path.read_bytes = _read_public_baseline_for_import
try:
    _spec = importlib.util.spec_from_file_location(
        "b0_calibration_logic_under_test", RUNNER_PATH
    )
    if _spec is None or _spec.loader is None:
        raise RuntimeError("could not load calibration provenance runner")
    calibration = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = calibration
    _spec.loader.exec_module(calibration)
finally:
    Path.read_bytes = _original_read_bytes
    if _prior_traci is None:
        sys.modules.pop("traci", None)
    else:
        sys.modules["traci"] = _prior_traci

if _intercept_count != 1:
    raise RuntimeError("calibration import did not use exactly one public B0 source")


QUALIFIES = "QUALIFIES"
DOES_NOT_QUALIFY = "DOES_NOT_QUALIFY"
NOT_IDENTIFIABLE = "NOT_IDENTIFIABLE"
INTEGRITY_FAILURE = "INTEGRITY_FAILURE"


class DemandGenerationTests(unittest.TestCase):
    def test_one_x_seed_20260904_reproduces_original_route_file_hash(self) -> None:
        route_bytes, manifest = calibration.build_demand(1, 20260904)

        self.assertEqual(
            calibration.sha256_bytes(route_bytes),
            calibration.EXPECTED_ORIGINAL_ROUTE_SHA256,
        )
        self.assertEqual(manifest["scheduled_trip_count"], 180)
        self.assertEqual(set(manifest["trips_per_route"].values()), {15})

    def test_every_ladder_demand_is_exact_balanced_and_deterministic(self) -> None:
        for label, multiplier in calibration.DEMAND_LADDER:
            with self.subTest(candidate=label):
                departure_vectors: list[list[int]] = []
                route_bytes_by_seed: list[bytes] = []
                for seed in calibration.CALIBRATION_SEEDS:
                    first_bytes, first_manifest = calibration.build_demand(
                        multiplier, seed
                    )
                    second_bytes, second_manifest = calibration.build_demand(
                        multiplier, seed
                    )
                    self.assertEqual(first_bytes, second_bytes)
                    self.assertEqual(first_manifest, second_manifest)

                    root = ET.parse(BytesIO(first_bytes)).getroot()
                    routes = [
                        (node.attrib["id"], node.attrib["edges"])
                        for node in root.findall("route")
                    ]
                    vehicles = root.findall("vehicle")
                    departures = [int(node.attrib["depart"]) for node in vehicles]
                    route_counts = Counter(node.attrib["route"] for node in vehicles)
                    block_counts = Counter(value // 60 for value in departures)

                    self.assertEqual(routes, list(calibration.ROUTES))
                    self.assertFalse(root.findall("flow"))
                    self.assertFalse(root.findall("trip"))
                    self.assertEqual(len(vehicles), 180 * multiplier)
                    self.assertEqual(first_manifest["scheduled_trip_count"], 180 * multiplier)
                    self.assertEqual(set(route_counts.values()), {15 * multiplier})
                    self.assertEqual(set(block_counts.values()), {12 * multiplier})
                    self.assertEqual(len(block_counts), 15)
                    self.assertEqual(departures, sorted(departures))
                    self.assertEqual(len(departures), len(set(departures)))
                    self.assertEqual(departures[0], 0)
                    self.assertLess(departures[-1], 900)
                    self.assertEqual(
                        first_manifest["scheduled_structural_A1B1_trip_count"],
                        15 * multiplier,
                    )
                    self.assertTrue(first_manifest["routes_fixed_before_simulation"])
                    self.assertFalse(first_manifest["dynamic_rerouting"])
                    departure_vectors.append(departures)
                    route_bytes_by_seed.append(first_bytes)

                self.assertTrue(
                    all(values == departure_vectors[0] for values in departure_vectors)
                )
                self.assertEqual(len(set(route_bytes_by_seed)), 3)

    def test_demand_builder_rejects_noncontract_multiplier_and_seed(self) -> None:
        for multiplier in (0, 6):
            with self.subTest(multiplier=multiplier):
                with self.assertRaises(ValueError):
                    calibration.build_demand(multiplier, 20260904)
        with self.assertRaises(ValueError):
            calibration.build_demand(2, 20260907)

    def test_scheduled_A1B1_event_departures_scale_exactly(self) -> None:
        expected_by_label = {"2X": 10, "3X": 15, "4X": 20, "5X": 25}

        for label, multiplier in calibration.DEMAND_LADDER:
            for seed in calibration.CALIBRATION_SEEDS:
                with self.subTest(candidate=label, seed=seed):
                    _, manifest = calibration.build_demand(multiplier, seed)
                    event_trips = [
                        trip
                        for trip in manifest["scheduled_trips"]
                        if calibration.MONITORED_EDGE in trip["edges"]
                        and calibration.DISRUPTION_START
                        <= trip["scheduled_departure_seconds"]
                        < calibration.DISRUPTION_END
                    ]

                    self.assertEqual(
                        manifest[
                            "scheduled_structural_A1B1_departures_during_event"
                        ],
                        expected_by_label[label],
                    )
                    self.assertEqual(len(event_trips), expected_by_label[label])
                    self.assertEqual(
                        {trip["route_id"] for trip in event_trips}, {"row1_east"}
                    )

    def test_all_twelve_generated_demands_roundtrip_through_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for label, multiplier in calibration.DEMAND_LADDER:
                for seed in calibration.CALIBRATION_SEEDS:
                    with self.subTest(candidate=label, seed=seed):
                        candidate_root = root / label.lower() / f"seed-{seed}"
                        candidate_root.mkdir(parents=True)
                        route_path = candidate_root / "fixed-routes.rou.xml"
                        manifest_path = candidate_root / "demand-manifest.json"
                        route_bytes, manifest = calibration.build_demand(
                            multiplier, seed
                        )
                        manifest["route_file_identity"] = route_path.as_posix()
                        manifest["route_file_sha256"] = calibration.sha256_bytes(
                            route_bytes
                        )
                        route_path.write_bytes(route_bytes)
                        manifest_path.write_text(
                            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8",
                        )

                        receipt = calibration.validate_demand(
                            route_path, manifest_path, multiplier, seed
                        )

                        self.assertEqual(receipt["status"], "PASS")
                        self.assertEqual(receipt["seed"], seed)
                        self.assertEqual(receipt["multiplier"], multiplier)
                        self.assertEqual(
                            receipt["scheduled_trip_count"], 180 * multiplier
                        )
                        self.assertEqual(
                            receipt["route_file_sha256"],
                            manifest["route_file_sha256"],
                        )


class CommandBoundaryTests(unittest.TestCase):
    def build_command(self, run_dir: Path, route_path: Path) -> list[str]:
        original_route = calibration.CURRENT_ROUTE_FILE
        original_seed = calibration.CURRENT_SEED
        try:
            calibration.CURRENT_ROUTE_FILE = route_path
            calibration.CURRENT_SEED = calibration.CALIBRATION_SEEDS[-1]
            return calibration.build_calibration_sumo_command(run_dir)
        finally:
            calibration.CURRENT_ROUTE_FILE = original_route
            calibration.CURRENT_SEED = original_seed

    @staticmethod
    def write_execution_receipt(run_dir: Path, command: list[str]) -> None:
        (run_dir / "execution-receipt.json").write_text(
            json.dumps({"command": command}), encoding="utf-8"
        )

    def test_command_binds_candidate_route_but_freezes_sumo_randomness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            route_path = Path(
                "inputs/demand/5x/seed-20260906/fixed-routes.rou.xml"
            )
            command = self.build_command(run_dir, route_path)

        self.assertEqual(
            calibration.command_option(command, "--route-files"),
            route_path.as_posix(),
        )
        self.assertEqual(
            calibration.command_option(command, "--seed"),
            str(calibration.FROZEN_SUMO_SEED),
        )
        self.assertNotEqual(
            calibration.command_option(command, "--seed"),
            str(calibration.CALIBRATION_SEEDS[-1]),
        )
        self.assertEqual(calibration.command_option(command, "--random"), "false")
        self.assertEqual(
            calibration.command_option(command, "--device.rerouting.probability"),
            "0",
        )
        self.assertEqual(
            calibration.command_option(
                command, "--person-device.rerouting.probability"
            ),
            "0",
        )
        self.assertEqual(
            [item for item in command if "rerouting" in item],
            [
                "--device.rerouting.probability",
                "--person-device.rerouting.probability",
            ],
        )

    def test_receipt_boundary_rejects_changed_or_duplicate_required_options(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            route_path = Path(
                "inputs/demand/2x/seed-20260904/fixed-routes.rou.xml"
            )
            original = self.build_command(run_dir, route_path)
            self.write_execution_receipt(run_dir, original)
            self.assertTrue(
                calibration.command_preserves_calibration_boundary(
                    run_dir, route_path
                )["pass"]
            )

            for option, replacement in (
                ("--device.rerouting.probability", "1"),
                ("--person-device.rerouting.probability", "1"),
                ("--random", "true"),
            ):
                with self.subTest(option=option):
                    altered = original.copy()
                    altered[altered.index(option) + 1] = replacement
                    self.write_execution_receipt(run_dir, altered)
                    self.assertFalse(
                        calibration.command_preserves_calibration_boundary(
                            run_dir, route_path
                        )["pass"]
                    )

            duplicated = original + ["--random", "false"]
            self.write_execution_receipt(run_dir, duplicated)
            self.assertFalse(
                calibration.command_preserves_calibration_boundary(
                    run_dir, route_path
                )["pass"]
            )

    def test_receipt_boundary_rejects_unapproved_rerouting_options(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            route_path = Path(
                "inputs/demand/2x/seed-20260904/fixed-routes.rou.xml"
            )
            command = self.build_command(run_dir, route_path)
            command.extend(["--device.rerouting.period", "30"])
            self.write_execution_receipt(run_dir, command)

            result = calibration.command_preserves_calibration_boundary(
                run_dir, route_path
            )

        self.assertFalse(result["pass"])


class LifecycleTests(unittest.TestCase):
    @staticmethod
    def expected_observer_events() -> list[dict[str, object]]:
        return [
            {
                "event": "RESTRICTION_ACTIVATION",
                "observed_at_seconds": calibration.DISRUPTION_START,
                "lane_id": calibration.RESTRICTED_LANE,
            },
            {
                "event": "RESTORATION",
                "observed_at_seconds": calibration.DISRUPTION_END,
                "lane_id": calibration.RESTRICTED_LANE,
            },
        ]

    @staticmethod
    def expected_raw_events() -> list[dict[str, object]]:
        return [
            {
                "event": "APPLY_ONE_LANE_LOSS_CAPACITY_PROXY",
                "observed_simulation_time_seconds": calibration.DISRUPTION_START,
                "lane_id": calibration.RESTRICTED_LANE,
            },
            {
                "event": "RESTORE_ORIGINAL_PERMISSIONS",
                "observed_simulation_time_seconds": calibration.DISRUPTION_END,
                "lane_id": calibration.RESTRICTED_LANE,
            },
        ]

    @staticmethod
    def raw_result(events: list[dict[str, object]], disrupted: bool) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            (run_dir / "disruption-events.json").write_text(
                json.dumps({"events": events}), encoding="utf-8"
            )
            return calibration.exact_raw_disruption_lifecycle(run_dir, disrupted)

    def test_observer_lifecycle_accepts_only_the_exact_permission_sequence(self) -> None:
        expected = self.expected_observer_events()
        self.assertTrue(
            calibration.exact_observer_permission_lifecycle(expected, True)["pass"]
        )
        self.assertTrue(
            calibration.exact_observer_permission_lifecycle([], False)["pass"]
        )

        extras = (
            {
                "event": "PERMISSION_CHANGE",
                "observed_at_seconds": 450,
                "lane_id": calibration.RESTRICTED_LANE,
            },
            {
                "event": "RESTRICTION_ACTIVATION",
                "observed_at_seconds": calibration.DISRUPTION_START,
                "lane_id": calibration.RESTRICTED_LANE,
            },
            {
                "event": "RESTORATION",
                "observed_at_seconds": calibration.DISRUPTION_END,
                "lane_id": calibration.SURVIVING_LANE,
            },
        )
        for extra in extras:
            with self.subTest(extra=extra):
                self.assertFalse(
                    calibration.exact_observer_permission_lifecycle(
                        expected + [extra], True
                    )["pass"]
                )

    def test_raw_lifecycle_rejects_every_extra_event(self) -> None:
        expected = self.expected_raw_events()
        self.assertTrue(self.raw_result(expected, True)["pass"])
        self.assertTrue(self.raw_result([], False)["pass"])

        for extra in (
            {
                "event": "EMERGENCY_FINALLY_RESTORATION",
                "observed_simulation_time_seconds": calibration.DISRUPTION_END,
                "lane_id": calibration.RESTRICTED_LANE,
            },
            {
                "event": "TRACI_CLOSE_ERROR",
                "observed_simulation_time_seconds": calibration.H_PILOT,
                "lane_id": None,
            },
        ):
            with self.subTest(extra=extra):
                self.assertFalse(self.raw_result(expected + [extra], True)["pass"])

        self.assertFalse(
            self.raw_result(
                [
                    {
                        "event": "UNEXPECTED_N0_EVENT",
                        "observed_simulation_time_seconds": 1,
                        "lane_id": calibration.RESTRICTED_LANE,
                    }
                ],
                False,
            )["pass"]
        )


class LocalResponseTests(unittest.TestCase):
    @staticmethod
    def visit(
        *, period: str = "DURING", edge_time: int = 10, halting: int = 0
    ) -> dict[str, object]:
        return {
            "edge_id": calibration.MONITORED_EDGE,
            "entry_period": period,
            "entry_observed_at_seconds": 350,
            "observed_edge_time_seconds": edge_time,
            "observed_halting_seconds": halting,
        }

    def response(
        self,
        *,
        exposed_ids: list[str],
        n0_visits: dict[str, list[dict[str, object]]],
        d0_visits: dict[str, list[dict[str, object]]],
        n0_arrivals: dict[str, int | None],
        d0_arrivals: dict[str, int | None],
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            n0_dir = root / "n0"
            d0_dir = root / "d0"
            n0_dir.mkdir()
            d0_dir.mkdir()
            n0_summary = {
                "unique_edge_entries": {"during": []},
                "per_vehicle": {
                    vehicle_id: {"edge_visits": visits}
                    for vehicle_id, visits in n0_visits.items()
                },
            }
            d0_summary = {
                "unique_edge_entries": {"during": exposed_ids},
                "per_vehicle": {
                    vehicle_id: {"edge_visits": visits}
                    for vehicle_id, visits in d0_visits.items()
                },
            }
            n0_ledger = {
                vehicle_id: {
                    "valid_non_teleported_arrival_seconds": arrival
                }
                for vehicle_id, arrival in n0_arrivals.items()
            }
            d0_ledger = {
                vehicle_id: {
                    "valid_non_teleported_arrival_seconds": arrival
                }
                for vehicle_id, arrival in d0_arrivals.items()
            }
            for directory, summary, ledger in (
                (n0_dir, n0_summary, n0_ledger),
                (d0_dir, d0_summary, d0_ledger),
            ):
                (directory / "exposure-summary.json").write_text(
                    json.dumps(summary), encoding="utf-8"
                )
                (directory / "vehicle-ledger.json").write_text(
                    json.dumps(ledger), encoding="utf-8"
                )
            return calibration.paired_local_response(n0_dir, d0_dir)

    def test_positive_witness_dominates_another_vehicle_ambiguity(self) -> None:
        result = self.response(
            exposed_ids=["witness", "ambiguous"],
            n0_visits={
                "witness": [self.visit(edge_time=10)],
                "ambiguous": [],
            },
            d0_visits={
                "witness": [self.visit(edge_time=11)],
                "ambiguous": [self.visit(edge_time=10)],
            },
            n0_arrivals={"witness": 500, "ambiguous": None},
            d0_arrivals={"witness": 500, "ambiguous": None},
        )

        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["local_physical_response_observed"])
        self.assertEqual(result["vehicles_with_local_physical_response"], ["witness"])
        self.assertEqual(
            result["unidentifiable_comparisons"][0]["vehicle_id"], "ambiguous"
        )

    def test_missing_arrival_is_ambiguous_without_an_edge_witness(self) -> None:
        result = self.response(
            exposed_ids=["unfinished"],
            n0_visits={"unfinished": [self.visit(edge_time=10, halting=2)]},
            d0_visits={"unfinished": [self.visit(edge_time=10, halting=2)]},
            n0_arrivals={"unfinished": 500},
            d0_arrivals={"unfinished": None},
        )

        self.assertEqual(result["status"], "NOT_IDENTIFIABLE")
        self.assertIsNone(result["local_physical_response_observed"])
        self.assertFalse(
            result["comparisons"][0]["final_arrival_comparison_identifiable"]
        )
        self.assertEqual(
            result["unidentifiable_comparisons"][0]["reason"],
            "NO_EDGE_WITNESS_AND_FINAL_ARRIVAL_COMPARISON_UNAVAILABLE",
        )

    def test_edge_witness_remains_positive_when_arrivals_are_missing(self) -> None:
        result = self.response(
            exposed_ids=["unfinished"],
            n0_visits={"unfinished": [self.visit(edge_time=10, halting=2)]},
            d0_visits={"unfinished": [self.visit(edge_time=10, halting=3)]},
            n0_arrivals={"unfinished": None},
            d0_arrivals={"unfinished": None},
        )

        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["local_physical_response_observed"])
        self.assertEqual(
            result["vehicles_with_local_physical_response"], ["unfinished"]
        )

    def test_fully_observed_equal_pair_is_a_definite_negative(self) -> None:
        result = self.response(
            exposed_ids=["equal"],
            n0_visits={"equal": [self.visit(edge_time=10, halting=2)]},
            d0_visits={"equal": [self.visit(edge_time=10, halting=2)]},
            n0_arrivals={"equal": 500},
            d0_arrivals={"equal": 500},
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["local_physical_response_observed"])


class QualificationBoundaryTests(unittest.TestCase):
    @staticmethod
    def qualifying_observation() -> dict[str, object]:
        return {
            "integrity_pass": True,
            "n0_completion_fraction": Fraction(99, 100),
            "n0_teleport_events": 0,
            "d0_completion_fraction": Fraction(95, 100),
            "d0_teleport_events": 0,
            "d0_exposure_count": 10,
            "mean_trip_time_difference_seconds": Fraction(1, 1),
            "queue_burden_relative_change": Fraction(1, 20),
            "local_physical_response_observed": True,
        }

    def test_all_inclusive_threshold_boundaries_qualify(self) -> None:
        result = calibration.qualification_from_observations(
            self.qualifying_observation()
        )

        self.assertTrue(result["qualifies"])
        self.assertEqual(result["failed_checks"], [])
        self.assertEqual(result["status"], QUALIFIES)

    def test_one_integer_below_each_completion_boundary_fails(self) -> None:
        cases = (
            ("n0_completion_fraction", Fraction(356, 360)),
            ("d0_completion_fraction", Fraction(341, 360)),
            ("n0_completion_fraction", Fraction(534, 540)),
            ("d0_completion_fraction", Fraction(512, 540)),
            ("n0_completion_fraction", Fraction(712, 720)),
            ("d0_completion_fraction", Fraction(683, 720)),
            ("n0_completion_fraction", Fraction(890, 900)),
            ("d0_completion_fraction", Fraction(854, 900)),
        )
        for key, value in cases:
            with self.subTest(key=key, value=value):
                observation = self.qualifying_observation()
                observation[key] = value
                result = calibration.qualification_from_observations(observation)
                self.assertFalse(result["qualifies"])
                self.assertEqual(result["status"], DOES_NOT_QUALIFY)

    def test_values_infinitesimally_below_threshold_do_not_round_up(self) -> None:
        cases = (
            ("n0_completion_fraction", Fraction(99, 100)),
            ("d0_completion_fraction", Fraction(95, 100)),
            ("mean_trip_time_difference_seconds", Fraction(1, 1)),
            ("queue_burden_relative_change", Fraction(1, 20)),
        )
        tiny = Fraction(1, 10**100)
        for key, boundary in cases:
            with self.subTest(key=key):
                just_below = boundary - tiny
                self.assertEqual(float(just_below), float(boundary))
                observation = self.qualifying_observation()
                observation[key] = just_below
                result = calibration.qualification_from_observations(observation)
                self.assertFalse(result["qualifies"])
                self.assertEqual(result["status"], DOES_NOT_QUALIFY)

    def test_exposure_nine_fails_and_ten_passes(self) -> None:
        for count, expected in ((9, False), (10, True)):
            with self.subTest(count=count):
                observation = self.qualifying_observation()
                observation["d0_exposure_count"] = count
                result = calibration.qualification_from_observations(observation)
                self.assertEqual(result["qualifies"], expected)

    def test_zero_queue_denominator_is_not_identifiable_not_a_weak_signal(self) -> None:
        observation = self.qualifying_observation()
        observation["queue_burden_relative_change"] = None

        result = calibration.qualification_from_observations(observation)

        self.assertFalse(result["qualifies"])
        self.assertEqual(result["status"], NOT_IDENTIFIABLE)

    def test_unknown_local_response_is_not_coerced_to_false(self) -> None:
        observation = self.qualifying_observation()
        observation["local_physical_response_observed"] = None

        result = calibration.qualification_from_observations(observation)

        self.assertFalse(result["qualifies"])
        self.assertEqual(result["status"], NOT_IDENTIFIABLE)

    def test_integrity_failure_has_its_own_status(self) -> None:
        observation = self.qualifying_observation()
        observation["integrity_pass"] = False

        result = calibration.qualification_from_observations(observation)

        self.assertFalse(result["qualifies"])
        self.assertEqual(result["status"], INTEGRITY_FAILURE)


class TriStateAggregationTests(unittest.TestCase):
    def test_all_three_seed_passes_qualify(self) -> None:
        self.assertEqual(
            calibration.aggregate_seed_qualification_statuses(
                [QUALIFIES, QUALIFIES, QUALIFIES]
            ),
            QUALIFIES,
        )

    def test_definite_scientific_failure_dominates_ambiguity(self) -> None:
        self.assertEqual(
            calibration.aggregate_seed_qualification_statuses(
                [QUALIFIES, NOT_IDENTIFIABLE, DOES_NOT_QUALIFY]
            ),
            DOES_NOT_QUALIFY,
        )

    def test_unknown_without_definite_failure_is_not_identifiable(self) -> None:
        self.assertEqual(
            calibration.aggregate_seed_qualification_statuses(
                [QUALIFIES, NOT_IDENTIFIABLE, QUALIFIES]
            ),
            NOT_IDENTIFIABLE,
        )

    def test_integrity_failure_dominates_every_other_seed_state(self) -> None:
        self.assertEqual(
            calibration.aggregate_seed_qualification_statuses(
                [DOES_NOT_QUALIFY, NOT_IDENTIFIABLE, INTEGRITY_FAILURE]
            ),
            INTEGRITY_FAILURE,
        )


class RecoveryDiagnosticTests(unittest.TestCase):
    @staticmethod
    def write_trace(path: Path, default: int, overrides: dict[int, int] | None = None) -> None:
        overrides = overrides or {}
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(
                [
                    "simulation_time_seconds",
                    "halting_vehicle_count_speed_below_0.1_mps",
                ]
            )
            for timestamp in range(1, calibration.H_PILOT + 1):
                writer.writerow([f"{timestamp}.0", overrides.get(timestamp, default)])

    def diagnostic(
        self,
        *,
        n0_default: int = 0,
        d0_default: int = 0,
        n0_overrides: dict[int, int] | None = None,
        d0_overrides: dict[int, int] | None = None,
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            n0 = root / "n0"
            d0 = root / "d0"
            n0.mkdir()
            d0.mkdir()
            self.write_trace(n0 / "step-trace.csv", n0_default, n0_overrides)
            self.write_trace(d0 / "step-trace.csv", d0_default, d0_overrides)
            return calibration.recovery_diagnostic(n0, d0)

    def test_no_positive_excess_has_no_recovery_signal(self) -> None:
        result = self.diagnostic(n0_default=2, d0_default=1)

        self.assertEqual(result["status"], "NO_RECOVERY_SIGNAL")
        self.assertEqual(result["maximum_positive_excess_queue_vehicles"], 0)
        self.assertIsNone(result["earliest_peak_time_seconds"])
        self.assertFalse(result["declines_after_peak"])

    def test_positive_peak_then_decline_is_observed(self) -> None:
        result = self.diagnostic(
            d0_overrides={601: 6, 602: 4, 603: 1, 604: 0}
        )

        self.assertEqual(result["status"], "RECOVERY_SIGNAL_OBSERVED")
        self.assertEqual(result["maximum_positive_excess_queue_vehicles"], 6)
        self.assertEqual(result["earliest_peak_time_seconds"], 601.0)
        self.assertTrue(result["declines_after_peak"])
        self.assertTrue(result["returns_to_zero_or_near_zero_before_h_pilot"])
        self.assertEqual(
            result["first_zero_or_near_zero_time_after_peak_seconds"], 603.0
        )

    def test_positive_excess_without_decline_has_no_recovery_signal(self) -> None:
        result = self.diagnostic(d0_default=5)

        self.assertEqual(result["status"], "NO_RECOVERY_SIGNAL")
        self.assertEqual(result["maximum_positive_excess_queue_vehicles"], 5)
        self.assertEqual(result["earliest_peak_time_seconds"], 601.0)
        self.assertFalse(result["declines_after_peak"])
        self.assertFalse(result["returns_to_zero_or_near_zero_before_h_pilot"])

    def test_negative_signed_difference_counts_as_zero_positive_excess(self) -> None:
        result = self.diagnostic(
            n0_default=5,
            d0_default=5,
            d0_overrides={601: 10, 602: 2},
        )

        self.assertEqual(result["status"], "RECOVERY_SIGNAL_OBSERVED")
        self.assertTrue(result["returns_to_zero_or_near_zero_before_h_pilot"])
        self.assertEqual(
            result["first_zero_or_near_zero_time_after_peak_seconds"], 602.0
        )

    def test_near_zero_only_at_horizon_is_not_before_horizon(self) -> None:
        result = self.diagnostic(d0_default=5, d0_overrides={1500: 0})

        self.assertEqual(result["status"], "RECOVERY_SIGNAL_OBSERVED")
        self.assertTrue(result["declines_after_peak"])
        self.assertFalse(result["returns_to_zero_or_near_zero_before_h_pilot"])
        self.assertIsNone(result["first_zero_or_near_zero_time_after_peak_seconds"])

    def test_incomplete_trace_returns_not_identifiable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            n0 = root / "n0"
            d0 = root / "d0"
            n0.mkdir()
            d0.mkdir()
            self.write_trace(n0 / "step-trace.csv", 0)
            self.write_trace(d0 / "step-trace.csv", 0)
            lines = (d0 / "step-trace.csv").read_text(encoding="utf-8").splitlines()
            (d0 / "step-trace.csv").write_text(
                "\n".join(lines[:-1]) + "\n", encoding="utf-8"
            )

            result = calibration.recovery_diagnostic(n0, d0)

        self.assertEqual(result["status"], "NOT_IDENTIFIABLE")


class FirstQualifyingSelectionTests(unittest.TestCase):
    def test_selects_first_qualifier_and_marks_higher_levels_not_run(self) -> None:
        result = calibration.first_qualifying_decision(
            {
                "2X": DOES_NOT_QUALIFY,
                "3X": QUALIFIES,
                "4X": QUALIFIES,
                "5X": QUALIFIES,
            }
        )

        self.assertEqual(result["decision"], "SELECTED")
        self.assertEqual(result["selected_level"], "3X")
        self.assertEqual(result["evaluated_levels"], ["2X", "3X"])
        self.assertEqual(result["not_run_levels"], ["4X", "5X"])

    def test_ambiguity_stops_before_a_higher_possible_qualifier(self) -> None:
        result = calibration.first_qualifying_decision(
            {
                "2X": NOT_IDENTIFIABLE,
                "3X": QUALIFIES,
                "4X": QUALIFIES,
                "5X": QUALIFIES,
            }
        )

        self.assertEqual(result["decision"], "INCONCLUSIVE")
        self.assertEqual(result["selected_level"], "NONE")
        self.assertEqual(result["evaluated_levels"], ["2X"])
        self.assertEqual(result["not_run_levels"], ["3X", "4X", "5X"])

    def test_integrity_failure_stops_the_ladder(self) -> None:
        result = calibration.first_qualifying_decision(
            {
                "2X": INTEGRITY_FAILURE,
                "3X": QUALIFIES,
                "4X": QUALIFIES,
                "5X": QUALIFIES,
            }
        )

        self.assertEqual(result["decision"], "FAIL")
        self.assertEqual(result["selected_level"], "NONE")
        self.assertEqual(result["evaluated_levels"], ["2X"])

    def test_all_definitive_failures_yield_no_qualifying_level(self) -> None:
        result = calibration.first_qualifying_decision(
            {label: DOES_NOT_QUALIFY for label, _ in calibration.DEMAND_LADDER}
        )

        self.assertEqual(result["decision"], "NO_QUALIFYING_DEMAND_LEVEL")
        self.assertEqual(result["selected_level"], "NONE")
        self.assertEqual(
            result["evaluated_levels"],
            [label for label, _ in calibration.DEMAND_LADDER],
        )
        self.assertEqual(result["not_run_levels"], [])


if __name__ == "__main__":
    unittest.main()
