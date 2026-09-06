"""Synthetic, workspace-local writer tests; no simulator or process launches."""

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from scripts.b0.od_integration_v1 import evidence


_RUNS = {}


def actual_run(kind):
    if kind not in _RUNS:
        from b0_od_integration_fixtures import good_record
        options = {"valid": {}, "overflow": {"waiting_overflow": True, "queue_budget": 0},
                   "deficient": {"missing_output": True}}[kind]
        _RUNS[kind] = good_record(**options)
    return copy.deepcopy(_RUNS[kind])


def failure_payload(raw=None):
    return {
        "schema_version": 1,
        "integration_identity": "B0_OD_INTEGRATION_LAYER_V1",
        "evidence_kind": "SYNTHETIC",
        "ready_to_run": False,
        "record_kind": "FAILURE",
        "record": {"failure_code": "SYNTHETIC_TECHNICAL_FAILURE", "measurement_status": None,
                   "run": None, "raw_evidence": raw},
    }


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        parent = evidence.WORKSPACE / "synthetic-test-outputs"
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="writer-", dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.payload = failure_payload({"waitingTime": None, "measurement_available": False})
        self.name = "synthetic.json"

    def receipt(self, payload=None, name=None):
        raw = (json.dumps(self.payload if payload is None else payload, ensure_ascii=False,
                          allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        return {"schema_version": 1, "evidence_kind": "SYNTHETIC", "ready_to_run": False,
                "persistence_status": "VERIFIED", "output_directory": str(self.output.relative_to(evidence.WORKSPACE)),
                "name": name or self.name, "format": "JSON", "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_count": len(raw)}

    def assert_incomplete(self, receipt=None):
        with self.assertRaises(evidence.EvidenceError):
            evidence.readback(self.receipt() if receipt is None else receipt)

    def test_failure_roundtrip_keeps_scientific_failure_and_nulls(self):
        receipt = evidence.write_once(self.output, self.name, self.payload)
        self.assertEqual(receipt, self.receipt())
        decoded = evidence.readback(receipt)
        self.assertEqual(decoded, self.payload)
        self.assertEqual(decoded["record_kind"], "FAILURE")
        self.assertIsNone(decoded["record"]["raw_evidence"]["waitingTime"])
        self.assertIs(decoded["ready_to_run"], False)
        self.assertFalse((self.output / (self.name + ".pending")).exists())

    def test_deterministic_utf8_and_one_terminal_newline(self):
        payload = failure_payload({"label": "synthetic Δ", "b": 2, "a": 1})
        receipt = evidence.write_once(self.output, self.name, payload)
        expected = (json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True,
                               separators=(",", ":")) + "\n").encode("utf-8")
        self.assertEqual((self.output / self.name).read_bytes(), expected)
        self.assertEqual(receipt["sha256"], hashlib.sha256(expected).hexdigest())
        self.assertFalse(expected.endswith(b"\n\n"))

    def test_raw_nonfinite_is_not_stringified_and_has_separate_failure_receipt(self):
        for index, value in enumerate((float("nan"), float("inf"), -float("inf"))):
            with self.subTest(value=index):
                name = "nonfinite-" + str(index) + ".json"
                payload = failure_payload({"waitingTime": value})
                with self.assertRaises(evidence.EvidenceError) as caught:
                    evidence.write_once(self.output, name, payload)
                error = caught.exception
                self.assertEqual(error.code, "SERIALIZATION_FAILURE")
                self.assertEqual(error.experiment_status, "FAIL")
                self.assertIsNotNone(error.failure_receipt_name)
                failure = json.loads((self.output / error.failure_receipt_name).read_text())
                self.assertEqual(failure["failure_code"], "SERIALIZATION_FAILURE")
                self.assertIs(failure["completed"], False)
                self.assertIs(failure["payload_preserved"], False)
                self.assertNotIn("waitingTime", failure)
                self.assertFalse((self.output / name).exists())
                self.assertFalse((self.output / (name + ".complete.json")).exists())
                self.assertIs(payload["record"]["raw_evidence"]["waitingTime"], value)

    def test_schema_identity_types_and_status_rejected_before_data_creation(self):
        cases = [
            {"schema_version": True}, {"integration_identity": "OTHER"},
            {"evidence_kind": "REAL"}, {"ready_to_run": True},
            {"record_kind": "PASS"}, {"extra": "unapproved"},
        ]
        for index, replacement in enumerate(cases):
            with self.subTest(index=index):
                payload = copy.deepcopy(self.payload)
                payload.update(replacement)
                name = "invalid-" + str(index) + ".json"
                with self.assertRaises(evidence.EvidenceError):
                    evidence.write_once(self.output, name, payload)
                self.assertFalse((self.output / name).exists())

    def test_failure_record_cannot_declare_valid_measurement(self):
        payload = copy.deepcopy(self.payload)
        payload["record"]["measurement_status"] = "VALID"
        with self.assertRaises(evidence.EvidenceError):
            evidence.write_once(self.output, self.name, payload)
        self.assertFalse((self.output / self.name).exists())

    def test_non_json_type_is_not_implicitly_converted(self):
        payload = failure_payload({"sequence": (1, 2)})
        with self.assertRaises(evidence.EvidenceError):
            evidence.write_once(self.output, self.name, payload)

    def test_actual_valid_run_roundtrip_reuses_production_accounting(self):
        run = actual_run("valid")
        self.assertEqual(run["measurement"]["measurement_status"], "VALID")
        self.assertEqual(run["measurement"]["metrics"]["scheduled_trips"], 540)
        self.assertEqual(run["measurement"]["metrics"]["restricted_mean_trip_time_seconds"], 101)
        payload = {**evidence.BASE, "record_kind": "RUN", "record": run}
        receipt = evidence.write_once(self.output, self.name, payload)
        self.assertEqual(evidence.readback(receipt), payload)

    def test_actual_waiting_overflow_roundtrips_only_as_failure(self):
        run = actual_run("overflow")
        measured = run["measurement"]
        self.assertEqual(measured["measurement_status"], "INTEGRITY_FAILURE")
        self.assertIn("AGGREGATE_NATIVE_WAITING_NONFINITE", measured["integrity_errors"])
        self.assertIsNone(measured["metrics"]["sumo_tripinfo_waiting_time_seconds_total"])
        with self.assertRaises(evidence.EvidenceError):
            evidence.write_once(self.output, "unsafe-run.json", {**evidence.BASE, "record_kind": "RUN", "record": run})
        payload = {**evidence.BASE, "record_kind": "FAILURE", "record": {
            "failure_code": "SYNTHETIC_WAITING_OVERFLOW", "measurement_status": "INTEGRITY_FAILURE",
            "run": run, "raw_evidence": None}}
        receipt = evidence.write_once(self.output, self.name, payload)
        decoded = evidence.readback(receipt)
        self.assertEqual(decoded, payload)
        self.assertEqual(decoded["record"]["run"]["measurement"], measured)
        self.assertIsNone(decoded["record"]["run"]["measurement"]["metrics"]["sumo_tripinfo_waiting_time_seconds_total"])

    def test_actual_missing_output_preserves_deficiency_and_original_evidence(self):
        run = actual_run("deficient")
        self.assertEqual(run["measurement"]["measurement_status"], "EVIDENCE_DEFICIENCY")
        self.assertIs(run["output_finalized"], False)
        payload = {**evidence.BASE, "record_kind": "FAILURE", "record": {
            "failure_code": "SYNTHETIC_MISSING_OUTPUT", "measurement_status": "EVIDENCE_DEFICIENCY",
            "run": run, "raw_evidence": None}}
        receipt = evidence.write_once(self.output, self.name, payload)
        self.assertEqual(evidence.readback(receipt), payload)

    def test_actual_valid_run_cannot_be_relabelled_as_invalid_failure(self):
        run = actual_run("valid")
        payload = {**evidence.BASE, "record_kind": "FAILURE", "record": {
            "failure_code": "SYNTHETIC_FALSE_FAILURE", "measurement_status": "INTEGRITY_FAILURE",
            "run": run, "raw_evidence": None}}
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.write_once(self.output, self.name, payload)
        self.assertEqual(caught.exception.code, "FAILURE_STATUS_CONTRADICTION")

    def test_actual_nonfinite_raw_value_is_retained_in_memory_not_serialized(self):
        run = actual_run("overflow")
        run["observations"]["tripinfo_records"][0]["waitingTime"] = float("nan")
        payload = {**evidence.BASE, "record_kind": "FAILURE", "record": {
            "failure_code": "SYNTHETIC_NONFINITE_RAW", "measurement_status": "INTEGRITY_FAILURE",
            "run": run, "raw_evidence": None}}
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.write_once(self.output, self.name, payload)
        self.assertEqual(caught.exception.code, "SERIALIZATION_FAILURE")
        self.assertFalse((self.output / self.name).exists())
        self.assertIsNotNone(caught.exception.failure_receipt_name)

    def test_unsafe_names_and_outside_directory_rejected(self):
        for name in ("../escape.json", "nested/data.json", "/absolute.json", "x..json", "x.xml"):
            with self.subTest(name=name), self.assertRaises(evidence.EvidenceError):
                evidence.write_once(self.output, name, self.payload)
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.write_once(evidence.WORKSPACE.parent, self.name, self.payload)
        self.assertEqual(caught.exception.code, "OUTPUT_OUTSIDE_WORKSPACE")
        self.assertEqual(list(self.output.iterdir()), [])

    def test_existing_data_pending_or_marker_never_overwritten(self):
        for index, suffix in enumerate(("", ".pending", ".complete.json")):
            with self.subTest(suffix=suffix):
                name = "existing-" + str(index) + ".json"
                existing = self.output / (name + suffix)
                existing.write_bytes(b"PRESERVE_SYNTHETIC_BYTES")
                before = set(self.output.iterdir())
                with self.assertRaises(evidence.EvidenceError) as caught:
                    evidence.write_once(self.output, name, self.payload)
                self.assertEqual(caught.exception.code, "DESTINATION_CONFLICT")
                self.assertEqual(existing.read_bytes(), b"PRESERVE_SYNTHETIC_BYTES")
                self.assertEqual(set(self.output.iterdir()), before)

    def test_second_write_preserves_first_completed_record(self):
        receipt = evidence.write_once(self.output, self.name, self.payload)
        before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        with self.assertRaises(evidence.EvidenceError):
            evidence.write_once(self.output, self.name, failure_payload({"different": True}))
        self.assertEqual({path.name: path.read_bytes() for path in self.output.iterdir()}, before)
        self.assertEqual(evidence.readback(receipt), self.payload)

    def test_symlink_destination_and_dangling_destination_rejected(self):
        target = self.output / "target.txt"
        target.write_text("PRESERVE")
        for index, destination in enumerate((target, self.output / "absent.txt")):
            with self.subTest(index=index):
                name = "link-" + str(index) + ".json"
                (self.output / name).symlink_to(destination)
                with self.assertRaises(evidence.EvidenceError):
                    evidence.write_once(self.output, name, self.payload)
                self.assertTrue((self.output / name).is_symlink())
        self.assertEqual(target.read_text(), "PRESERVE")

    def test_symlink_parent_is_rejected_without_following_it(self):
        real = self.output / "real"
        real.mkdir()
        alias = self.output / "alias"
        alias.symlink_to(real, target_is_directory=True)
        with self.assertRaises(evidence.EvidenceError):
            evidence.write_once(alias, self.name, self.payload)
        self.assertEqual(list(real.iterdir()), [])

    def test_short_data_write_keeps_pending_and_cannot_complete(self):
        original = os.write
        calls = 0

        def short_second(descriptor, raw):
            nonlocal calls
            calls += 1
            return original(descriptor, raw[:len(raw) // 2] if calls == 2 else raw)

        with patch.object(evidence.os, "write", side_effect=short_second):
            with self.assertRaises(evidence.EvidenceError) as caught:
                evidence.write_once(self.output, self.name, self.payload)
        self.assertEqual(caught.exception.code, "SHORT_WRITE")
        self.assertEqual(caught.exception.experiment_status, "BLOCKED")
        self.assertTrue((self.output / (self.name + ".pending")).exists())
        self.assertFalse((self.output / (self.name + ".complete.json")).exists())
        self.assert_incomplete()

    def test_short_marker_write_keeps_pending_and_cannot_complete(self):
        original = os.write
        calls = 0

        def short_third(descriptor, raw):
            nonlocal calls
            calls += 1
            return original(descriptor, raw[:len(raw) // 2] if calls == 3 else raw)

        with patch.object(evidence.os, "write", side_effect=short_third):
            with self.assertRaises(evidence.EvidenceError):
                evidence.write_once(self.output, self.name, self.payload)
        self.assertTrue((self.output / (self.name + ".pending")).exists())
        self.assert_incomplete()

    def test_data_fsync_failure_does_not_complete(self):
        original = os.fsync
        calls = 0

        def fail_second(descriptor):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic fsync failure")
            return original(descriptor)

        with patch.object(evidence.os, "fsync", side_effect=fail_second):
            with self.assertRaises(evidence.EvidenceError) as caught:
                evidence.write_once(self.output, self.name, self.payload)
        self.assertEqual(caught.exception.experiment_status, "BLOCKED")
        self.assert_incomplete()

    def test_failed_data_readback_never_creates_completion_marker(self):
        original = evidence._read

        def corrupt(directory, name):
            raw = original(directory, name)
            return raw + b" " if name == self.name else raw

        with patch.object(evidence, "_read", side_effect=corrupt):
            with self.assertRaises(evidence.EvidenceError) as caught:
                evidence.write_once(self.output, self.name, self.payload)
        self.assertEqual(caught.exception.code, "READBACK_MISMATCH")
        self.assertFalse((self.output / (self.name + ".complete.json")).exists())
        self.assert_incomplete()

    def test_failed_marker_readback_leaves_latch_even_if_marker_bytes_are_valid(self):
        original = evidence._read

        def corrupt(directory, name):
            raw = original(directory, name)
            return raw + b" " if name == self.name + ".complete.json" else raw

        with patch.object(evidence, "_read", side_effect=corrupt):
            with self.assertRaises(evidence.EvidenceError) as caught:
                evidence.write_once(self.output, self.name, self.payload)
        self.assertEqual(caught.exception.code, "MARKER_READBACK_MISMATCH")
        self.assertTrue((self.output / (self.name + ".complete.json")).exists())
        self.assertTrue((self.output / (self.name + ".pending")).exists())
        self.assert_incomplete()

    def test_final_latch_removal_failure_does_not_complete(self):
        with patch.object(evidence.os, "unlink", side_effect=OSError("synthetic unlink failure")):
            with self.assertRaises(evidence.EvidenceError) as caught:
                evidence.write_once(self.output, self.name, self.payload)
        self.assertEqual(caught.exception.experiment_status, "BLOCKED")
        self.assertTrue((self.output / (self.name + ".pending")).exists())
        self.assert_incomplete()

    def test_directory_close_failure_precedes_completion_and_keeps_latch(self):
        original_create, original_close = evidence._create, os.close
        target = {"descriptor": None, "failed": False}

        def track(directory, name, raw):
            if name == self.name + ".pending":
                target["descriptor"] = directory
            return original_create(directory, name, raw)

        def fail_outer_close(descriptor):
            if (descriptor == target["descriptor"] and not target["failed"]
                    and (self.output / (self.name + ".complete.json")).exists()):
                target["failed"] = True
                raise OSError("synthetic outer directory close failure")
            return original_close(descriptor)

        try:
            with patch.object(evidence, "_create", side_effect=track), patch.object(evidence.os, "close", side_effect=fail_outer_close):
                with self.assertRaises(evidence.EvidenceError) as caught:
                    evidence.write_once(self.output, self.name, self.payload)
            self.assertTrue(target["failed"])
            self.assertEqual(caught.exception.experiment_status, "BLOCKED")
        finally:
            if target["failed"]:
                original_close(target["descriptor"])
        self.assertTrue((self.output / (self.name + ".pending")).exists())
        self.assertTrue((self.output / (self.name + ".complete.json")).exists())
        self.assert_incomplete()

    def test_independent_readback_detects_data_corruption(self):
        receipt = evidence.write_once(self.output, self.name, self.payload)
        (self.output / self.name).write_bytes(b"{}\n")
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.readback(receipt)
        self.assertEqual(caught.exception.code, "READBACK_MISMATCH")

    def test_independent_readback_rejects_missing_marker(self):
        receipt = evidence.write_once(self.output, self.name, self.payload)
        (self.output / (self.name + ".complete.json")).unlink()
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.readback(receipt)
        self.assertEqual(caught.exception.code, "READBACK_MISSING")

    def test_independent_readback_rejects_modified_receipt(self):
        receipt = evidence.write_once(self.output, self.name, self.payload)
        for key, value in (("sha256", "0" * 64), ("byte_count", receipt["byte_count"] + 1),
                           ("ready_to_run", True), ("output_directory", "../outside")):
            with self.subTest(key=key), self.assertRaises(evidence.EvidenceError):
                evidence.readback({**receipt, key: value})

    def test_xml_uses_same_completion_and_independent_validator(self):
        raw = b'<routes><vehicle id="synthetic_0"/></routes>\n'
        calls = []

        def validate(value):
            calls.append(value)
            root = ET.fromstring(value)
            if root.tag != "routes" or root[0].attrib != {"id": "synthetic_0"}:
                raise ValueError("synthetic XML mismatch")

        receipt = evidence.write_input_once(self.output, "synthetic.rou.xml", raw, validate)
        self.assertEqual(receipt["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(evidence.readback(receipt, validator=validate), raw)
        self.assertGreaterEqual(len(calls), 3)
        with self.assertRaises(evidence.EvidenceError):
            evidence.readback(receipt)

    def test_xml_revalidation_failure_withholds_completion(self):
        raw = b"<routes/>\n"
        calls = 0

        def fail_readback(value):
            nonlocal calls
            calls += 1
            ET.fromstring(value)
            if calls == 2:
                raise ValueError("synthetic independent validation failure")

        with self.assertRaises(evidence.EvidenceError):
            evidence.write_input_once(self.output, "synthetic.rou.xml", raw, fail_readback)
        self.assertTrue((self.output / "synthetic.rou.xml.pending").exists())
        self.assertTrue((self.output / "synthetic.rou.xml.complete.json").exists())

    def test_xml_requires_validator_and_frozen_newline(self):
        cases = ((b"<routes/>\n", None), (b"<routes/>", ET.fromstring),
                 (b"<routes/>\n\n", ET.fromstring))
        for index, (raw, validator) in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(evidence.EvidenceError):
                evidence.write_input_once(self.output, "invalid-" + str(index) + ".xml", raw, validator)


if __name__ == "__main__":
    unittest.main()
