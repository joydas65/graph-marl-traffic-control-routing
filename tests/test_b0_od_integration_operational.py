"""Actual-core, fake-only abort regressions; no live-runtime claims."""

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.b0.od_integration_v1 import evidence, integration as core, qualification as q
from b0_od_integration_fixtures import FakeBackend
from test_b0_od_integration_qualification import record, pairs


class OperationalAbortTests(unittest.TestCase):
    def assert_stop(self, run, expected="BLOCKED"):
        assessed = core.assess_run(run)
        self.assertEqual(assessed["stop_status"], expected, assessed["reason_codes"])
        self.assertNotEqual(assessed["measurement"]["measurement_status"], "VALID")
        other = record("D0" if run["condition_label"] == "N0" else "N0")
        pair = (run, other) if run["condition_label"] == "N0" else (other, run)
        with patch.object(q.cutoff_measurement, "paired_local_response",
                          side_effect=AssertionError("aborted pair must not evaluate gates")):
            result = q.qualify_pair(*pair)
        self.assertEqual(result["stop_status"], expected)
        self.assertFalse(result["qualification_evaluated"])
        self.assertEqual(result["gates"], {})
        return result

    def test_first_advance_abort_preserves_failure_and_stops(self):
        binding = core.build_binding(core.repository_root(), 20260904, "C1")
        backend = FakeBackend(binding, fail_step=0)
        run = core.observe_run(binding, "N0", "SYNTHETIC-FIRST-ABORT", backend, backend)
        self.assertEqual(run["failure"], {"kind": "TECHNICAL", "stage": "OBSERVATION", "code": "OSError"})
        self.assertEqual(run["observations"]["step_intervals"], [])
        self.assertEqual(run["observations"]["queue_trace"], [])
        self.assertEqual(backend.log, [("advance", 0), ("close", 0), ("output", 0)])
        self.assertEqual(run["cleanup_failures"], [])
        self.assertTrue(backend.closed)
        self.assertEqual(self.assert_stop(run)["pair_status"], "OPERATIONAL_BLOCKED")
        session = q.SelectionSession(); incoming = pairs("C1")
        incoming[0] = (run, incoming[0][1])
        self.assertEqual(session.add_level("C1", incoming)["status"], "BLOCKED")
        for level in ("C1", "C2"):
            with self.subTest(level=level), self.assertRaises(ValueError):
                session.add_level(level, [])
        with self.assertRaises(ValueError):
            session.add_repeats(None, None)
        with self.assertRaises(ValueError):
            session.finalize(None)

    def test_valid_prefix_and_event_boundaries_remain_unusable_without_retry(self):
        for role, end in (("N0", 50), ("D0", 300), ("D0", 350), ("D0", 600), ("D0", 1499)):
            with self.subTest(role=role, end=end):
                run = record(role, fail_step=end)
                prefix = record(role)
                self.assertEqual(run["controls"]["steps"], prefix["controls"]["steps"][:end])
                self.assertEqual(run["observations"]["step_intervals"], [[t,t+1] for t in range(end)])
                self.assertEqual(run["failure"]["code"], "OSError")
                self.assertIsNone(run["summary"])
                self.assertIsNone(run["preactivation"])
                self.assertFalse(run["observations"]["observations_complete"])
                self.assert_stop(run)

    def test_technical_label_or_missing_boundary_is_not_sufficient(self):
        for mutation in ("no_proof", "no_readback", "advanced_clock", "wrong_operation", "false_complete", "false_final", "false_measurement"):
            with self.subTest(mutation=mutation):
                run = record(fail_step=50)
                if mutation == "no_proof": run["operational_abort"] = None
                elif mutation == "no_readback": run["operational_abort"]["readback"] = None
                elif mutation == "advanced_clock": run["operational_abort"]["readback"]["time"] += 1
                elif mutation == "wrong_operation": run["operational_abort"]["operation"] = "UNSUPPORTED"
                elif mutation == "false_complete": run["observations"]["observations_complete"] = True
                elif mutation == "false_final": run["controls"]["final"] = run["controls"]["initial"]
                else: run["measurement"]["measurement_status"] = "VALID"
                self.assert_stop(run, "FAIL")

    def test_contradictory_prefix_cannot_hide_behind_expected_missing_tail(self):
        for mutation in ("queue", "halting", "active", "future_event", "monitor", "permissions", "collision", "config", "events", "lifecycle"):
            with self.subTest(mutation=mutation):
                run = record("D0", fail_step=350)
                obs, step = run["observations"], run["controls"]["steps"][20]
                if mutation == "queue": obs["queue_trace"][20][1] += 1
                elif mutation == "halting": obs["per_trip_halting_seconds"]["veh_0000"] += 1
                elif mutation == "active": step["active_ids"] = []
                elif mutation == "future_event": obs["departed_events"]["veh_0000"] = [351]
                elif mutation == "monitor": step["monitor_states"] = {}
                elif mutation == "permissions": step["permissions"]["A1B1_1"]["disallowed"] = ["passenger"]
                elif mutation == "collision": step["diagnostics"]["collisions"] = 1
                elif mutation == "config": step["controls_sha256"] = "0" * 64
                elif mutation == "events": run["events"]["events"].pop()
                else: run["lifecycle"][0]["time"] += 1
                run["measurement"] = core._account(run)
                self.assert_stop(run, "FAIL")

    def test_binding_and_boundary_contradictions_fail(self):
        for field in ("controls", "diagnostics", "active_ids", "permissions"):
            with self.subTest(field=field):
                run = record(fail_step=50)
                boundary = run["operational_abort"]["readback"]
                boundary[field] = [] if field == "active_ids" else {}
                self.assert_stop(run, "FAIL")
        for field in ("route_file_sha256", "implementation_sha256", "scientific_configuration"):
            with self.subTest(binding=field):
                run = record(fail_step=50); run["binding"][field] = "CHANGED"
                self.assertEqual(q.qualify_pair(run, record("D0"))["stop_status"], "FAIL")

    def test_observed_overflow_collision_and_forbidden_lane_keep_fail_precedence(self):
        for options in ({"waiting_overflow": True}, {"collision_at": 20}):
            with self.subTest(options=options):
                self.assert_stop(record(fail_step=50, **options), "FAIL")
        self.assert_stop(record("D0", fail_step=350, restricted_entry=True), "FAIL")

    def test_abort_boundary_can_independently_establish_collision_or_changed_control(self):
        # At t=0 there was no prior diagnostic sample: the abort readback matters.
        self.assert_stop(record(fail_step=0, collision_at=0), "FAIL")
        binding = core.build_binding(core.repository_root(), 20260904, "C1")
        class ChangedAfterAbort(FakeBackend):
            def simulationStep(self):
                self.control_snapshot["scientific_configuration"]["dynamic_rerouting"] = True
                raise OSError("synthetic abort with forbidden control")
        backend = ChangedAfterAbort(binding)
        self.assert_stop(core.observe_run(binding, "N0", "SYNTHETIC-CHANGED-CONTROL", backend, backend), "FAIL")

    def test_incomplete_readback_or_partial_advance_is_not_supported(self):
        binding = core.build_binding(core.repository_root(), 20260904, "C1")
        class Advanced(FakeBackend):
            def simulationStep(self):
                self.time += 1
                raise OSError("synthetic ambiguous advance")
        backend = Advanced(binding)
        self.assert_stop(core.observe_run(binding, "N0", "SYNTHETIC-PARTIAL-ADVANCE", backend, backend), "FAIL")

    def test_missing_output_and_cleanup_after_supported_abort_do_not_make_valid(self):
        for options in ({"missing_output": True}, {"close_failure": True}):
            with self.subTest(options=options):
                self.assert_stop(record(fail_step=50, **options))

    def test_independent_other_run_and_seed_failure_precede_blocked(self):
        aborted = record(fail_step=0)
        self.assertEqual(q.qualify_pair(aborted, record("D0", waiting_overflow=True))["stop_status"], "FAIL")
        incoming = pairs("C1"); incoming[0] = (aborted, incoming[0][1])
        incoming[1] = (record(seed=20260905, waiting_overflow=True), incoming[1][1])
        self.assertEqual(q.SelectionSession().add_level("C1", incoming)["status"], "FAIL")

    def test_blocked_repeat_stops_and_revalidates_without_selection(self):
        session = q.SelectionSession(); session.add_level("C1", pairs("C1"))
        decision = session.add_repeats(record("N0-CAL-R", fail_step=50), record("D0-CAL-R"))
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertIsNone(decision["selected_calibrated_od_concentration"])
        self.assertEqual(q.validate_selection_record(session.to_record()), decision)
        with self.assertRaises(ValueError): session.add_repeats(None, None)
        with self.assertRaises(ValueError): session.finalize(None)

    def test_blocked_failure_and_session_survive_writer_and_readback_not_pass(self):
        run = record(fail_step=50)
        session = q.SelectionSession(); incoming = pairs("C1"); incoming[0] = (run, incoming[0][1])
        session.add_level("C1", incoming)
        parent = evidence.WORKSPACE / "synthetic-test-outputs"; parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            output = Path(temporary)
            failure = {**evidence.BASE, "record_kind": "FAILURE", "record": {
                "failure_code": "SUPPORTED_OPERATIONAL_ABORT", "experiment_status": "BLOCKED",
                "measurement_status": core.validate_run(run)["measurement_status"], "run": run, "raw_evidence": None}}
            receipt = evidence.write_once(output, "abort.json", failure)
            self.assertEqual(evidence.readback(receipt), failure)
            self.assertEqual(receipt["persistence_status"], "VERIFIED")
            payload = {**evidence.BASE, "record_kind": "SELECTION", "record": session.to_record()}
            saved = evidence.write_once(output, "selection.json", payload)
            self.assertEqual(evidence.readback(saved), payload)
            self.assertEqual(session.decision["status"], "BLOCKED")
            with self.assertRaises(ValueError): session.finalize(saved)
            changed = copy.deepcopy(payload); changed["record"]["decision"]["status"] = "PASS"
            with self.assertRaises((ValueError, evidence.EvidenceError)):
                evidence.write_once(output, "false-pass.json", changed)
            for label in (None, "PASS", "FAIL"):
                with self.subTest(label=label):
                    bad = copy.deepcopy(failure)
                    if label is None: del bad["record"]["experiment_status"]
                    else: bad["record"]["experiment_status"] = label
                    with self.assertRaises(evidence.EvidenceError):
                        evidence.write_once(output, "bad-"+str(label)+".json", bad)
            # Corrupted stored bytes retain readback FAIL, never BLOCKED/PASS.
            (output / "abort.json").write_bytes(b"{}\n")
            with self.assertRaises(evidence.EvidenceError) as caught:
                evidence.readback(receipt)
            self.assertEqual(caught.exception.experiment_status, "FAIL")


if __name__ == "__main__":
    unittest.main()
