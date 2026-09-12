"""Characterize an unsupported live-finalization boundary; NOT acceptance tests.

All observations, terminal errors and processes here are synthetic. Passing
these tests demonstrates why implementation stopped, not live compatibility.
Run with python3 -I -S -B tests/test_od_live_binding_finalization_boundary.py.
The existing offline harness denies simulator imports, process/socket access,
and output writes outside its isolated synthetic workspace.
"""

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
import run_b0_od_integration_offline as safety
from b0_od_integration_fixtures import FakeBackend, good_record
from scripts.b0.od_integration_v1 import evidence, integration as core, qualification


class SyntheticTerminalIntegrityError(ValueError):
    """An injected positive contradiction, not absent/malformed TripInfo."""


class FinalizationDouble(FakeBackend):
    def __init__(self, binding, *, mode="reject_output", fail_step=None):
        super().__init__(binding, fail_step=fail_step)
        self.mode = mode
        self.terminal_evidence = None
        self.original_xml = None

    def close(self, wait=True):
        super().close(wait=wait)
        # No real process: the double makes an independently known error
        # available only after the last pre-close observation/readback.
        self.terminal_evidence = {
            "evidence_kind": "SYNTHETIC", "process_finalized": True,
            "exit_code": 1, "positive_integrity_contradiction": True,
            "diagnostic": "SYNTHETIC_FINALIZED_OUTPUT_IDENTITY_CONTRADICTION",
        }
        if self.mode == "reject_close":
            raise SyntheticTerminalIntegrityError("synthetic terminal contradiction")

    def finalize_output(self):
        self.original_xml = super().finalize_output()
        if self.terminal_evidence is None:
            raise AssertionError("terminal evidence accessed before finalization")
        if self.mode == "reject_output":
            raise SyntheticTerminalIntegrityError("synthetic terminal contradiction")
        return self.original_xml


def observed(*, mode="reject_output", fail_step=None):
    binding = core.build_binding(ROOT, 20260904, "C1")
    backend = FinalizationDouble(binding, mode=mode, fail_step=fail_step)
    run = core.observe_run(binding, "N0", "SYNTHETIC-FINALIZATION-BOUNDARY", backend, backend)
    return run, backend


class FinalizationBoundaryCharacterization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.complete, cls.complete_backend = observed()
        cls.aborted, cls.aborted_backend = observed(fail_step=50)
        cls.other = good_record(condition_label="D0")

    def test_full_horizon_positive_terminal_contradiction_becomes_inconclusive(self):
        run = self.complete
        self.assertTrue(run["observations"]["observations_complete"])
        self.assertEqual(len(core.adapter.parse_tripinfo_xml(self.complete_backend.original_xml)), 540)
        self.assertTrue(self.complete_backend.terminal_evidence["positive_integrity_contradiction"])
        self.assertEqual(run["failure"], {"kind": "EVIDENCE", "stage": "TRIPINFO_FINALIZATION",
                                        "code": "SyntheticTerminalIntegrityError"})
        assessed = core.assess_run(run)
        self.assertEqual(assessed["measurement"]["measurement_status"], "EVIDENCE_DEFICIENCY")
        self.assertEqual(assessed["stop_status"], "INCONCLUSIVE")
        self.assertEqual(qualification.qualify_pair(run, self.other)["stop_status"], "INCONCLUSIVE")

    def test_abort_retains_first_failure_but_terminal_contradiction_is_not_represented(self):
        run = self.aborted
        self.assertEqual(run["failure"], {"kind": "TECHNICAL", "stage": "OBSERVATION", "code": "OSError"})
        self.assertEqual(run["operational_abort"]["readback"]["time"], 50)
        self.assertTrue(self.aborted_backend.terminal_evidence["positive_integrity_contradiction"])
        self.assertEqual(core.assess_run(run)["stop_status"], "BLOCKED")
        self.assertEqual(qualification.qualify_pair(run, self.other)["stop_status"], "BLOCKED")
        self.assertNotEqual(core.validate_run(run)["measurement_status"], "VALID")
        self.assertEqual(run["cleanup_failures"], [])
        self.assertNotIn("SyntheticTerminalIntegrityError", json.dumps(run))

    def test_close_exception_does_not_provide_independent_fail_precedence(self):
        for stop_at, expected in ((None, "INCONCLUSIVE"), (50, "BLOCKED")):
            with self.subTest(stop_at=stop_at):
                run, backend = observed(mode="reject_close", fail_step=stop_at)
                self.assertTrue(backend.terminal_evidence["positive_integrity_contradiction"])
                self.assertEqual(run["cleanup_failures"], [{"stage": "CONNECTION_CLOSE",
                                                         "code": "SyntheticTerminalIntegrityError"}])
                self.assertEqual(core.assess_run(run)["stop_status"], expected)

    def test_returning_valid_xml_cannot_carry_the_missing_terminal_diagnostic(self):
        # This is the UNSAFE alternative, deliberately not a proposed binding.
        run, backend = observed(mode="return_xml")
        self.assertTrue(backend.terminal_evidence["positive_integrity_contradiction"])
        self.assertEqual(core.validate_run(run)["measurement_status"], "VALID")
        self.assertTrue(qualification.qualify_pair(run, self.other)["qualification_evaluated"])
        self.assertNotIn("terminal_evidence", run)

    def test_observation_diagnostics_end_before_finalization(self):
        for run, backend, clock in ((self.complete, self.complete_backend, 1500),
                                    (self.aborted, self.aborted_backend, 50)):
            with self.subTest(clock=clock):
                self.assertEqual(backend.log[-2:], [("close", clock), ("output", clock)])
                self.assertTrue(all(step["diagnostics"] == {
                    "collisions": 0, "invalid_routes": 0, "simulator_errors": 0}
                    for step in run["controls"]["steps"]))
                self.assertTrue(backend.terminal_evidence["process_finalized"])

    def test_raw_evidence_persists_but_does_not_change_revalidated_status(self):
        # Strict writer/readback, no PASS stub. The persisted contradiction is
        # intentionally not interpreted by the accepted FAILURE schema.
        run = self.aborted
        payload = {**evidence.BASE, "record_kind": "FAILURE", "record": {
            "failure_code": "SYNTHETIC_UNSUPPORTED_TERMINAL_DIAGNOSTIC",
            "measurement_status": core.validate_run(run)["measurement_status"],
            "experiment_status": "BLOCKED", "run": run,
            "raw_evidence": self.aborted_backend.terminal_evidence}}
        with tempfile.TemporaryDirectory(prefix="terminal-boundary-", dir=safety.OUTPUTS) as temporary:
            receipt = evidence.write_once(Path(temporary), "synthetic-boundary.json", payload)
            read = evidence.readback(receipt)
            self.assertEqual(read, payload)
            self.assertEqual(read["record"]["experiment_status"], "BLOCKED")
            self.assertEqual(receipt["evidence_kind"], "SYNTHETIC")
            self.assertFalse(receipt["ready_to_run"])
            contradicted = copy.deepcopy(payload)
            contradicted["record"]["experiment_status"] = "FAIL"
            with self.assertRaises(evidence.EvidenceError) as caught:
                evidence.write_once(Path(temporary), "synthetic-forced-fail.json", contradicted)
            self.assertEqual(caught.exception.code, "FAILURE_EXPERIMENT_STATUS_CONTRADICTION")

    def test_arbitrary_run_extension_is_not_an_authorized_schema_workaround(self):
        run = copy.deepcopy(self.aborted)
        run["terminal_evidence"] = self.aborted_backend.terminal_evidence
        with self.assertRaisesRegex(ValueError, "RUN_SCHEMA"):
            core.validate_run(run)


if __name__ == "__main__":
    before = safety.hashes()
    own_before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(FinalizationBoundaryCharacterization)
    result = unittest.TextTestRunner(verbosity=2, resultclass=safety.Counted).run(suite)
    unchanged = before == safety.hashes() and own_before == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = {"surface": "FINALIZATION_BOUNDARY_CHARACTERIZATION_NOT_BINDING_ACCEPTANCE",
              "tests": result.testsRun, "passed": result.passed, "subtests": result.subtests,
              "failures": len(result.failures), "errors": len(result.errors),
              "skips": len(result.skipped), "collection_errors": len(loader.errors),
              "forbidden_attempts": safety.attempts, "source_hashes_unchanged": unchanged,
              "new_test_sha256": own_before, "accepted_source_sha256": before}
    print("OFFLINE_REPORT=" + json.dumps(report), flush=True)
    raise SystemExit(0 if result.wasSuccessful() and not loader.errors and not safety.attempts and unchanged else 1)
