"""Independent integer boundary answers through genuine offline V2 accounting."""

import copy
from b0_od_integration_fixtures import REFERENCES, observe
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.b0.od_integration_v1 import integration, qualification as q
from b0_od_integration_fixtures import good_record


_RECORDS = {}
SEEDS = (20260904, 20260905, 20260906)
LEVELS = ("C1", "C2", "C3", "C4")


def record(condition="N0", seed=SEEDS[0], level="C1", **options):
    key = (condition, seed, level, tuple(sorted(options.items())))
    if key not in _RECORDS:
        _RECORDS[key] = good_record(seed=seed, level=level,
                                    condition_label=condition, **options)
    return copy.deepcopy(_RECORDS[key])


def pairs(level, *, qualify=True):
    return [(record("N0", seed, level), record("D0", seed, level, **(
        {} if qualify else {"arrival_delta_total": 0, "queue_budget": 540}))) for seed in SEEDS]


class QualificationTests(unittest.TestCase):
    def test_default_pair_has_hand_computable_exact_thresholds(self):
        result = q.qualify_pair(record(), record("D0"), references=REFERENCES)
        self.assertEqual(result["pair_status"], "QUALIFIES")
        self.assertEqual(result["exact_restricted_sum_difference"], {"numerator": 540, "denominator": 1})
        self.assertEqual(result["queue_totals"], {"N0": 540, "D0": 567})
        self.assertTrue(all(value is True for value in result["gates"].values()))

    def test_completion_thresholds_below_equal_above_are_inclusive(self):
        for role, arrivals in (("N0", (534, 535, 536)), ("D0", (512, 513, 514))):
            for count, expected in zip(arrivals, (False, True, True)):
                with self.subTest(role=role, arrivals=count):
                    n0, d0 = record(), record("D0")
                    changed = record(role, active_count=540-count)
                    if role == "N0":
                        n0 = changed
                    else:
                        d0 = changed
                    self.assertEqual(integration.validate_run(changed, references=REFERENCES)["measurement_status"], "VALID")
                    decision = q.qualify_pair(n0, d0, references=REFERENCES)
                    self.assertIs(decision["gates"][role.lower()+"_completion"], expected)

    def test_exact_mean_sum_539_540_541_has_no_display_rounding(self):
        for total, expected in ((539, False), (540, True), (541, True)):
            with self.subTest(sum_difference=total):
                decision = q.qualify_pair(record(), record("D0", arrival_delta_total=total), references=REFERENCES)
                self.assertEqual(decision["exact_restricted_sum_difference"], {"numerator": total, "denominator": 1})
                self.assertIs(decision["gates"]["all_scheduled_restricted_time"], expected)

    def test_exact_queue_20_21_22_against_20(self):
        for queue, expected in ((20, False), (21, True), (22, True)):
            with self.subTest(queue=queue):
                decision = q.qualify_pair(record(queue_budget=20), record("D0", queue_budget=queue), references=REFERENCES)
                self.assertEqual(decision["queue_totals"], {"N0": 20, "D0": queue})
                self.assertIs(decision["gates"]["network_queue"], expected)

    def test_actual_exposure_9_10_11_not_planned_route_total(self):
        for exposed, expected in ((9, False), (10, True), (11, True)):
            with self.subTest(exposed=exposed):
                d0 = record("D0", exposure_count=exposed)
                self.assertEqual(d0["summary"]["unique_edge_entry_counts"]["during"], exposed)
                decision = q.qualify_pair(record(), d0, references=REFERENCES)
                self.assertIs(decision["gates"]["actual_event_entry_exposure"], expected)

    def test_zero_queue_is_unknown_not_zero_imputed(self):
        decision = q.qualify_pair(record(queue_budget=0), record("D0", queue_budget=1), references=REFERENCES)
        self.assertIsNone(decision["gates"]["network_queue"])
        self.assertEqual(decision["pair_status"], "NOT_IDENTIFIABLE")

    def test_censored_local_comparison_remains_unknown(self):
        n0 = record(queue_budget=20)
        d0 = record("D0", arrival_delta_total=0, queue_budget=21, censored_exposed_count=1)
        decision = q.qualify_pair(n0, d0, references=REFERENCES)
        self.assertEqual(decision["pair_status"], "NOT_IDENTIFIABLE")
        self.assertIsNone(decision["gates"]["local_physical_response"])
        self.assertEqual(decision["failed_gates"], [])

    def test_definite_scientific_failure_precedes_valid_local_unknown(self):
        n0 = record(queue_budget=20)
        d0 = record("D0", arrival_delta_total=0, queue_budget=21,
                    censored_exposed_count=1, active_count=28)
        decision = q.qualify_pair(n0, d0, references=REFERENCES)
        self.assertEqual(decision["pair_status"], "DOES_NOT_QUALIFY")
        self.assertIn("d0_completion", decision["failed_gates"])
        self.assertIn("local_physical_response", decision["unknown_gates"])

    def test_integrity_overflow_prevents_all_scientific_gates(self):
        with mock.patch.object(q.cutoff_measurement, "paired_local_response", side_effect=AssertionError("must not evaluate")):
            decision = q.qualify_pair(record(), record("D0", waiting_overflow=True), references=REFERENCES)
        self.assertEqual(decision["pair_status"], "INTEGRITY_FAILURE")
        self.assertEqual(decision["stop_status"], "FAIL")
        self.assertFalse(decision["qualification_evaluated"])
        self.assertEqual(decision["gates"], {})

    def test_deficiency_is_not_hidden_by_scientific_nonqualification(self):
        d0 = record("D0", missing_output=True, arrival_delta_total=0, queue_budget=0)
        decision = q.qualify_pair(record(), d0, references=REFERENCES)
        self.assertEqual(decision["pair_status"], "EVIDENCE_DEFICIENCY")
        self.assertEqual(decision["stop_status"], "INCONCLUSIVE")
        self.assertFalse(decision["qualification_evaluated"])
        self.assertEqual(decision["gates"], {})

    def test_valid_label_and_edited_metrics_do_not_bypass_revalidation(self):
        d0 = record("D0")
        d0["measurement"]["metrics"]["arrived_trips"] = 539
        d0["measurement"]["measurement_status"] = "VALID"
        self.assertEqual(q.qualify_pair(record(), d0, references=REFERENCES)["pair_status"], "INTEGRITY_FAILURE")
        d0 = record("D0", waiting_overflow=True)
        d0["measurement"]["measurement_status"] = "VALID"
        d0["measurement"]["integrity_errors"] = []
        self.assertEqual(q.qualify_pair(record(), d0, references=REFERENCES)["pair_status"], "INTEGRITY_FAILURE")

    def test_roles_duplicate_run_and_substituted_input_fail_closed(self):
        n0, d0 = record(), record("D0")
        self.assertEqual(q.qualify_pair(d0, n0, references=REFERENCES)["pair_status"], "INTEGRITY_FAILURE")
        duplicate = copy.deepcopy(d0); duplicate["run_id"] = n0["run_id"]
        self.assertEqual(q.qualify_pair(n0, duplicate, references=REFERENCES)["pair_status"], "INTEGRITY_FAILURE")
        changed = copy.deepcopy(d0); changed["binding"]["route_file_sha256"] = "0" * 64
        self.assertEqual(q.qualify_pair(n0, changed, references=REFERENCES)["pair_status"], "INTEGRITY_FAILURE")
        self.assertEqual(q.qualify_pair(n0, record("D0", seed=SEEDS[1]), references=REFERENCES)["pair_status"], "INTEGRITY_FAILURE")


class SelectionTests(unittest.TestCase):
    def test_first_qualifier_at_each_level_has_exact_bounded_evidence_counts(self):
        for index, target in enumerate(LEVELS):
            with self.subTest(first_qualifier=target):
                session = q.SelectionSession(references=REFERENCES)
                for earlier in LEVELS[:index]:
                    self.assertEqual(session.add_level(earlier, pairs(earlier, qualify=False))["status"], "CONTINUE")
                provisional = session.add_level(target, pairs(target))
                self.assertEqual(provisional["status"], "PROVISIONAL")
                self.assertEqual(provisional["provisional_level"], target)
                with self.assertRaises(ValueError):
                    session.add_level("C4", [])
                pending = session.add_repeats(record("N0-CAL-R", level=target), record("D0-CAL-R", level=target))
                self.assertEqual(pending["status"], "PENDING_READBACK")
                self.assertEqual(pending["scientific_records"] + pending["repeat_records"], (8, 14, 20, 26)[index])
                self.assertIsNone(pending["selected_calibrated_od_concentration"])
                self.assertFalse(pending["ready_to_run"])
                if target == "C4":
                    from scripts.b0.od_integration_v1 import evidence
                    envelope = {
                        "schema_version": 2, "integration_identity": "B0_OD_INTEGRATION_LAYER_V1",
                        "evidence_kind": "SYNTHETIC", "ready_to_run": False,
                        "record_kind": "SELECTION", "record": session.to_record(),
                    }
                    encoded = (json.dumps(envelope, ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
                    self.assertLessEqual(len(encoded) + 1024, evidence.MAX_BYTES)
                    print("SYNTHETIC_C4_PAYLOAD_BYTES=" + str(len(encoded)), flush=True)
                    output_root = evidence.WORKSPACE / "synthetic-test-outputs"
                    output_root.mkdir(parents=True, exist_ok=True)
                    with tempfile.TemporaryDirectory(prefix="full-c4-selection-", dir=output_root) as directory:
                        receipt = evidence.write_once(Path(directory), "selection.json", envelope, references=REFERENCES)
                        self.assertEqual(receipt["persistence_status"], "VERIFIED")
                        self.assertEqual(receipt["byte_count"], len(encoded))
                        self.assertEqual(receipt["sha256"], hashlib.sha256(encoded).hexdigest())
                        self.assertTrue(evidence.readback(receipt, references=REFERENCES) == envelope,
                                        "full C4 readback differs from the supplied synthetic selection")
                        accepted = session.finalize(receipt)
                        self.assertEqual(accepted["status"], "PASS")
                        self.assertEqual(accepted["evidence_kind"], "SYNTHETIC")
                        self.assertEqual(accepted["synthetic_selected_level"], "C4")
                        self.assertIs(accepted["readback_verified"], True)
                        self.assertIsNone(accepted["selected_calibrated_od_concentration"])
                        self.assertFalse(accepted["ready_to_run"])

    def test_all_four_definite_failures_produce_no_qualifier_without_repeat(self):
        session = q.SelectionSession(references=REFERENCES)
        for level in LEVELS:
            result = session.add_level(level, pairs(level, qualify=False))
        self.assertEqual(result["status"], "NO_QUALIFYING_OD_CONCENTRATION")
        self.assertEqual(result["scientific_records"], 24)
        self.assertEqual(result["repeat_records"], 0)
        with self.assertRaises(ValueError):
            session.add_level("C5", [])
        with self.assertRaises(ValueError):
            session.add_repeats({}, {})

    def test_missing_duplicate_out_of_order_or_mismatched_seed_evidence_rejected(self):
        complete = pairs("C1")
        for submitted in (complete[:2], [complete[0], complete[0], complete[2]],
                          [complete[1], complete[0], complete[2]]):
            with self.subTest(length=len(submitted)):
                with self.assertRaises(ValueError):
                    q.SelectionSession(references=REFERENCES).add_level("C1", submitted)
        with self.assertRaises(ValueError):
            q.SelectionSession(references=REFERENCES).add_level("C2", pairs("C2"))

    def test_definite_seed_failure_precedes_other_seed_scientific_unknown(self):
        submitted = pairs("C1")
        submitted[0] = (record(queue_budget=20), record("D0", arrival_delta_total=0, queue_budget=21, censored_exposed_count=1))
        submitted[1] = (record(seed=SEEDS[1]), record("D0", seed=SEEDS[1], arrival_delta_total=0, queue_budget=540))
        self.assertEqual(q.SelectionSession(references=REFERENCES).add_level("C1", submitted)["status"], "CONTINUE")

    def test_unknown_or_deficient_measurement_stops_without_searching_higher(self):
        submitted = pairs("C1")
        submitted[0] = (record(queue_budget=20), record("D0", arrival_delta_total=0, queue_budget=21, censored_exposed_count=1))
        session = q.SelectionSession(references=REFERENCES)
        self.assertEqual(session.add_level("C1", submitted)["status"], "INCONCLUSIVE")
        with self.assertRaises(ValueError):
            session.add_level("C2", [])
        submitted = pairs("C1", qualify=False)
        submitted[0] = (record(), record("D0", missing_output=True))
        self.assertEqual(q.SelectionSession(references=REFERENCES).add_level("C1", submitted)["status"], "INCONCLUSIVE")

    def test_integrity_failure_precedes_other_definitive_seed_failure(self):
        submitted = pairs("C1", qualify=False)
        submitted[0] = (record(), record("D0", waiting_overflow=True))
        self.assertEqual(q.SelectionSession(references=REFERENCES).add_level("C1", submitted)["status"], "FAIL")

    def test_repeat_mismatch_is_terminal_and_never_searches_higher(self):
        session = q.SelectionSession(references=REFERENCES); session.add_level("C1", pairs("C1"))
        result = session.add_repeats(record("N0-CAL-R"), record("D0-CAL-R", arrival_delta_total=541))
        self.assertEqual(result["status"], "FAIL")
        with self.assertRaises(ValueError):
            session.add_repeats({}, {})
        with self.assertRaises(ValueError):
            session.add_level("C2", [])

    def test_repeat_requires_first_seed_labels_and_fresh_ids(self):
        for n0, d0 in ((record(), record("D0")),
                       (record("N0-CAL-R", seed=SEEDS[1]), record("D0-CAL-R", seed=SEEDS[1]))):
            with self.subTest(seed=n0["binding"]["seed"], label=n0["condition_label"]):
                session = q.SelectionSession(references=REFERENCES); session.add_level("C1", pairs("C1"))
                self.assertEqual(session.add_repeats(n0, d0)["status"], "FAIL")

    def test_serialized_selection_is_recomputed_and_forged_pass_rejected(self):
        session = q.SelectionSession(references=REFERENCES); session.add_level("C1", pairs("C1"))
        session.add_repeats(record("N0-CAL-R"), record("D0-CAL-R"))
        payload = session.to_record()
        self.assertEqual(q.validate_selection_record(payload, references=REFERENCES)["status"], "PENDING_READBACK")
        payload["decision"]["status"] = "PASS"
        with self.assertRaises(ValueError):
            q.validate_selection_record(payload, references=REFERENCES)

    def test_readback_failure_prevents_acceptance_and_preserves_stop_class(self):
        from scripts.b0.od_integration_v1 import evidence
        for status in ("FAIL", "BLOCKED"):
            with self.subTest(status=status):
                session = q.SelectionSession(references=REFERENCES); session.add_level("C1", pairs("C1"))
                session.add_repeats(record("N0-CAL-R"), record("D0-CAL-R"))
                error = OSError("synthetic readback failure")
                error.experiment_status = status
                with mock.patch.object(evidence, "readback", side_effect=error):
                    with self.assertRaises(OSError):
                        session.finalize({})
                self.assertEqual(session.decision["status"], status)
                with self.assertRaises(ValueError):
                    session.finalize({})


if __name__ == "__main__":
    unittest.main()
