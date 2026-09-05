"""V2 numerical-boundary regressions; large values are not traffic evidence.

The exact C1 fixture preserves the reported 540-trip counterexample. Artificial
restricted-mean faults exercise the final metric guard; such overflow is not
reachable from valid frozen horizon/population bounds. Serialization belongs to
a later integration layer, so these tests use strict standard-library JSON.
"""

import builtins
from copy import deepcopy
import json
import math
import unittest
from unittest.mock import patch

from scripts.b0.od_concentration_v2 import cutoff_measurement
from b0_od_v2_fixtures import (
    exact_c1_fixture, WAITING_METRIC, GOLDEN_PAYLOAD_SHA256, payload_sha256,
)
from test_b0_od_trip_accounting_v2 import fixture


class AggregateFinitenessTests(unittest.TestCase):
    def assert_safe_metrics(self, result):
        for name, value in result["metrics"].items():
            if isinstance(value, float):
                self.assertTrue(math.isfinite(value), name)

    def assert_controlled_waiting_overflow(self, result):
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")
        self.assertIn("AGGREGATE_NATIVE_WAITING_NONFINITE", result["integrity_errors"])
        self.assertIsNone(result["metrics"][WAITING_METRIC])
        self.assertFalse(result["qualification_evaluated"])
        self.assert_safe_metrics(result)

    def test_normal_fifteen_and_zero_waiting_remain_valid(self):
        for total in (15, 0):
            with self.subTest(total=total):
                scheduled, parameters = fixture()
                if total == 0:
                    for row in parameters["tripinfo_records"]:
                        row["waitingTime"] = 0
                result = cutoff_measurement.account_trips(scheduled, **parameters)
                self.assertEqual(result["measurement_status"], "VALID")
                self.assertEqual(result["integrity_errors"], [])
                self.assertEqual(result["evidence_deficiencies"], [])
                self.assertEqual(result["metrics"][WAITING_METRIC], total)
                self.assert_safe_metrics(result)

    def test_two_individually_finite_waits_cannot_return_valid_overflow(self):
        scheduled, parameters = fixture()
        for row in parameters["tripinfo_records"][:2]:
            row["waitingTime"] = 1e308
            self.assertTrue(math.isfinite(row["waitingTime"]))
        result = cutoff_measurement.account_trips(scheduled, **parameters)
        self.assert_controlled_waiting_overflow(result)
        self.assertEqual(result["integrity_errors"], ["AGGREGATE_NATIVE_WAITING_NONFINITE"])
        self.assertEqual(result["evidence_deficiencies"], [])

    def test_large_but_finite_total_is_not_rejected_by_a_new_magnitude_rule(self):
        # Numerical guard coverage only, not a physically plausible trip wait.
        scheduled, parameters = fixture()
        parameters["tripinfo_records"][0]["waitingTime"] = 1e308
        result = cutoff_measurement.account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "VALID")
        self.assertEqual(result["metrics"][WAITING_METRIC], 1e308)
        self.assertEqual(payload_sha256(result), GOLDEN_PAYLOAD_SHA256["valid_large_finite"])
        self.assert_safe_metrics(result)
        json.dumps(result, allow_nan=False)

    def test_exact_540_c1_counterexample_is_controlled_on_v2(self):
        scheduled, parameters = exact_c1_fixture()
        result = cutoff_measurement.account_trips(scheduled, **parameters)
        self.assert_controlled_waiting_overflow(result)
        self.assertEqual(result["integrity_errors"], ["AGGREGATE_NATIVE_WAITING_NONFINITE"])
        self.assertEqual(result["evidence_deficiencies"], [])
        self.assertEqual(result["metrics"]["scheduled_trips"], 540)
        self.assertEqual(result["metrics"]["arrived_trips"], 540)
        self.assertEqual(result["metrics"]["unfinished_trips"], 0)
        self.assertEqual(result["metrics"]["restricted_mean_trip_time_seconds"], 101)
        self.assertEqual(result["metrics"]["restricted_p95_trip_time_seconds_nearest_rank"], 101)
        self.assertEqual(len(result["ledger"]), 540)
        self.assertEqual(set(result["ledger"]), {r["vehicle_id"] for r in scheduled})

    def test_overflow_preserves_all_rows_contributions_and_other_frozen_metrics(self):
        scheduled, parameters = exact_c1_fixture()
        new = cutoff_measurement.account_trips(scheduled, **parameters)
        self.assert_controlled_waiting_overflow(new)
        self.assertEqual(payload_sha256(new["ledger"]), GOLDEN_PAYLOAD_SHA256["overflow_c1_ledger"])
        self.assertEqual(
            payload_sha256({k: v for k, v in new["metrics"].items() if k != WAITING_METRIC}),
            GOLDEN_PAYLOAD_SHA256["overflow_c1_other_metrics"],
        )
        self.assertEqual(new["ledger"]["veh_0000"]["native_waiting_normalized_seconds"], 1e308)
        self.assertEqual(new["ledger"]["veh_0001"]["native_waiting_normalized_seconds"], 1e308)
        self.assertIsNone(new["metrics"][WAITING_METRIC])

    def test_diagnostic_is_deterministic_and_inputs_are_unchanged(self):
        scheduled, parameters = exact_c1_fixture()
        before = deepcopy((scheduled, parameters))
        first = cutoff_measurement.account_trips(scheduled, **parameters)
        second = cutoff_measurement.account_trips(scheduled, **parameters)
        self.assertEqual(first, second)
        self.assertEqual((scheduled, parameters), before)
        self.assert_controlled_waiting_overflow(first)

    def test_overflow_diagnostic_survives_an_additional_missing_wait_input(self):
        scheduled, parameters = fixture()
        for row in parameters["tripinfo_records"][:2]:
            row["waitingTime"] = 1e308
        del parameters["tripinfo_records"][3]["waitingTime"]
        result = cutoff_measurement.account_trips(scheduled, **parameters)
        self.assert_controlled_waiting_overflow(result)
        self.assertIn("NATIVE_WAITING_MISSING:d", result["evidence_deficiencies"])
        self.assertEqual(len(result["ledger"]), 4)

    def test_string_nan_and_infinity_retain_input_rejection(self):
        for value in ("NaN", "Infinity", "-Infinity", "nan", "inf"):
            with self.subTest(value=value):
                scheduled, parameters = fixture()
                parameters["tripinfo_records"][0]["waitingTime"] = value
                result = cutoff_measurement.account_trips(scheduled, **parameters)
                self.assertEqual(result["measurement_status"], "EVIDENCE_DEFICIENCY")
                self.assertIn("INVALID_NATIVE_WAITING:a", result["evidence_deficiencies"])
                self.assertIsNone(result["metrics"][WAITING_METRIC])
                self.assertEqual(result["ledger"]["a"]["raw_tripinfo"]["waitingTime"], value)
                self.assert_safe_metrics(result)
                self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)

    def test_numeric_nan_and_infinity_raw_evidence_requires_strict_output_rejection(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=repr(value)):
                scheduled, parameters = fixture()
                parameters["tripinfo_records"][0]["waitingTime"] = value
                result = cutoff_measurement.account_trips(scheduled, **parameters)
                self.assertEqual(result["measurement_status"], "EVIDENCE_DEFICIENCY")
                self.assertIn("INVALID_NATIVE_WAITING:a", result["evidence_deficiencies"])
                self.assertIsNone(result["metrics"][WAITING_METRIC])
                raw = result["ledger"]["a"]["raw_tripinfo"]["waitingTime"]
                self.assertFalse(math.isfinite(raw))
                self.assert_safe_metrics(result)
                # Invalid raw evidence is preserved, not converted into a string metric.
                json.dumps(result["metrics"], allow_nan=False)
                with self.assertRaises(ValueError):
                    json.dumps(result, allow_nan=False)

    def test_strict_json_roundtrip_for_valid_and_controlled_overflow_payloads(self):
        for make_fixture in (fixture, exact_c1_fixture):
            with self.subTest(fixture=make_fixture.__name__):
                scheduled, parameters = make_fixture()
                result = cutoff_measurement.account_trips(scheduled, **parameters)
                encoded = json.dumps(result, allow_nan=False, sort_keys=True)
                self.assertEqual(json.loads(encoded), result)
                self.assert_safe_metrics(result)

    def test_representative_valid_mixed_population_matches_frozen_output(self):
        scheduled, parameters = fixture()
        new = cutoff_measurement.account_trips(scheduled, **parameters)
        self.assertEqual(new["measurement_status"], "VALID")
        self.assertEqual(payload_sha256(new), GOLDEN_PAYLOAD_SHA256["valid_mixed"])

    def test_exact_c1_with_normal_waits_matches_frozen_output(self):
        scheduled, parameters = exact_c1_fixture()
        for row in parameters["tripinfo_records"]:
            row["waitingTime"] = 1
        new = cutoff_measurement.account_trips(scheduled, **parameters)
        self.assertEqual(new["measurement_status"], "VALID")
        self.assertEqual(new["metrics"][WAITING_METRIC], 540)
        self.assertEqual(payload_sha256(new), GOLDEN_PAYLOAD_SHA256["valid_c1_normal_waits"])

    def test_synthetic_unreachable_mean_fault_is_caught_by_final_metric_guard(self):
        # Frozen valid input bounds cannot overflow this mean. Inject only the
        # list sum used for restricted time, leaving all other sums untouched.
        for fault in (float("inf"), float("nan")):
            with self.subTest(fault=repr(fault)):
                scheduled, parameters = fixture()

                def fake_sum(values, *args, **kwargs):
                    if isinstance(values, list):
                        return fault
                    return builtins.sum(values, *args, **kwargs)

                with patch.object(cutoff_measurement, "sum", fake_sum, create=True):
                    result = cutoff_measurement.account_trips(scheduled, **parameters)
                self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")
                self.assertEqual(result["integrity_errors"], [
                    "AGGREGATE_METRIC_NONFINITE:restricted_mean_trip_time_seconds"
                ])
                self.assertIsNone(result["metrics"]["restricted_mean_trip_time_seconds"])
                self.assertEqual(result["metrics"][WAITING_METRIC], 15)
                self.assertFalse(result["qualification_evaluated"])
                self.assert_safe_metrics(result)
                self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)


if __name__ == "__main__":
    unittest.main()
