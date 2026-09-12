"""Synthetic origin-contract tests; no LIVE-labelled traffic evidence is created.

LIVE values below are deliberately fabricated metadata test vectors. Their raw
failure payloads identify that test-only purpose; they are not observations from
a native process, execution authorization, or real calibration results.
"""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from b0_od_integration_fixtures import REFERENCES
from test_b0_od_integration_qualification import pairs, record
from scripts.b0.od_integration_v1 import evidence, qualification as q


def raw_failure(origin):
    return {**evidence.PAYLOAD_BASE, "evidence_kind": origin,
            "record_kind": "FAILURE", "record": {
                "failure_code": "SYNTHETIC_ORIGIN_METADATA_TEST",
                "measurement_status": None, "run": None,
                "raw_evidence": {"fixture_origin": "SYNTHETIC",
                                 "purpose": "origin metadata validation only"}}}


class OriginPersistenceTests(unittest.TestCase):
    def setUp(self):
        parent = evidence.WORKSPACE / "synthetic-test-outputs"
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="origin-test-", dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)

    def test_explicit_origin_propagates_through_pending_marker_receipt_and_readback(self):
        original = evidence._create
        for origin in ("SYNTHETIC", "LIVE"):
            with self.subTest(origin_metadata_test_vector=origin):
                created = {}
                name = origin.lower() + "-metadata-test.json"

                def capture(directory, filename, raw):
                    created[filename] = raw
                    return original(directory, filename, raw)

                payload = raw_failure(origin)
                with patch.object(evidence, "_create", side_effect=capture):
                    receipt = evidence.write_once(self.output, name, payload)
                for value in (receipt, json.loads(created[name + ".pending"]),
                              json.loads(created[name + ".complete.json"])):
                    self.assertEqual(value["evidence_kind"], origin)
                    self.assertIs(value["ready_to_run"], False)
                self.assertEqual(evidence.readback(receipt), payload)
                self.assertFalse((self.output / (name + ".pending")).exists())

    def test_raw_failure_without_exact_origin_is_rejected_before_writing(self):
        for index, origin in enumerate((None, "REAL", "synthetic", True, ["LIVE"])):
            with self.subTest(index=index):
                payload = raw_failure(origin)
                if origin is None:
                    del payload["evidence_kind"]
                with self.assertRaises(evidence.EvidenceError):
                    evidence.write_once(self.output, str(index) + ".json", payload)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_failure_attempt_receipt_preserves_explicit_origin(self):
        for origin in ("SYNTHETIC", "LIVE"):
            with self.subTest(origin_metadata_test_vector=origin):
                payload = raw_failure(origin)
                payload["record"]["raw_evidence"]["unserializable"] = float("nan")
                with self.assertRaises(evidence.EvidenceError) as caught:
                    evidence.write_once(self.output, origin.lower() + ".json", payload)
                failure = json.loads((self.output / caught.exception.failure_receipt_name).read_bytes())
                self.assertEqual(failure["evidence_kind"], origin)
                self.assertEqual(failure["experiment_status"], "FAIL")
                self.assertIs(failure["completed"], False)
                self.assertIs(failure["ready_to_run"], False)

    def test_receipt_origin_substitution_rejected(self):
        receipt = evidence.write_once(self.output, "synthetic.json", raw_failure("SYNTHETIC"))
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.readback({**receipt, "evidence_kind": "LIVE"})
        self.assertEqual(caught.exception.code, "RECEIPT_MISMATCH")

    def test_marker_origin_substitution_rejected_even_with_matching_receipt(self):
        name = "synthetic.json"
        receipt = evidence.write_once(self.output, name, raw_failure("SYNTHETIC"))
        path = self.output / (name + ".complete.json")
        marker = json.loads(path.read_bytes())
        marker["evidence_kind"] = "LIVE"
        path.write_bytes(evidence._encode(marker))
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.readback({**receipt, "evidence_kind": "LIVE"})
        self.assertEqual(caught.exception.code, "EVIDENCE_ORIGIN_MISMATCH")

    def test_pending_origin_substitution_retains_incomplete_latch(self):
        name = "synthetic.json"
        original = evidence._read

        def substituted(directory, filename):
            raw = original(directory, filename)
            if filename == name + ".pending":
                pending = json.loads(raw)
                pending["evidence_kind"] = "LIVE"
                return evidence._encode(pending)
            return raw

        with patch.object(evidence, "_read", side_effect=substituted):
            with self.assertRaises(evidence.EvidenceError) as caught:
                evidence.write_once(self.output, name, raw_failure("SYNTHETIC"))
        self.assertEqual(caught.exception.code, "PENDING_ORIGIN_MISMATCH")
        self.assertTrue((self.output / (name + ".pending")).exists())

    def test_xml_explicit_origin_and_default_are_not_authorization(self):
        raw = b'<routes fixture="SYNTHETIC_ORIGIN_METADATA_TEST"/>\n'
        for origin in ("SYNTHETIC", "LIVE"):
            with self.subTest(origin_metadata_test_vector=origin):
                kwargs = {} if origin == "SYNTHETIC" else {"evidence_kind": origin}
                receipt = evidence.write_input_once(
                    self.output, origin.lower() + "-metadata-test.xml", raw,
                    lambda data: data == raw, **kwargs)
                self.assertEqual(receipt["evidence_kind"], origin)
                self.assertIs(receipt["ready_to_run"], False)
                self.assertEqual(evidence.readback(receipt, validator=lambda data: data == raw), raw)
                other = "LIVE" if origin == "SYNTHETIC" else "SYNTHETIC"
                with self.assertRaises(evidence.EvidenceError):
                    evidence.readback({**receipt, "evidence_kind": other}, validator=lambda data: data == raw)

    def test_run_and_failure_envelopes_cannot_relabel_synthetic_run(self):
        run = record()
        for kind in ("RUN", "FAILURE"):
            with self.subTest(kind=kind):
                payload = raw_failure("LIVE")
                payload["record_kind"] = kind
                if kind == "RUN":
                    payload["record"] = run
                else:
                    payload["record"]["run"] = run
                with self.assertRaises(evidence.EvidenceError) as caught:
                    evidence.write_once(self.output, kind.lower() + ".json", payload, references=REFERENCES)
                self.assertEqual(caught.exception.code, "EVIDENCE_ORIGIN_MISMATCH")

    def test_selection_envelope_origin_must_match_record(self):
        session = q.SelectionSession(references=REFERENCES)
        session.add_level("C1", pairs("C1"))
        payload = {**evidence.PAYLOAD_BASE, "evidence_kind": "LIVE",
                   "record_kind": "SELECTION", "record": session.to_record()}
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.write_once(self.output, "selection.json", payload, references=REFERENCES)
        self.assertEqual(caught.exception.code, "EVIDENCE_ORIGIN_MISMATCH")


class OriginQualificationTests(unittest.TestCase):
    def test_default_actual_synthetic_pair_and_session_keep_origin(self):
        incoming = pairs("C1")
        pair = q.qualify_pair(*incoming[0], references=REFERENCES)
        self.assertEqual(pair["pair_status"], "QUALIFIES")
        self.assertEqual(pair["evidence_kind"], "SYNTHETIC")
        session = q.SelectionSession(references=REFERENCES)
        self.assertEqual(session.add_level("C1", incoming)["evidence_kind"], "SYNTHETIC")
        self.assertEqual(session.to_record()["evidence_kind"], "SYNTHETIC")

    def test_explicit_session_origin_is_not_execution_or_selection(self):
        for origin in ("SYNTHETIC", "LIVE"):
            with self.subTest(origin_metadata_test_vector=origin):
                session = q.SelectionSession(evidence_kind=origin)
                for value in (session.decision, session.to_record()):
                    self.assertEqual(value["evidence_kind"], origin)
                    self.assertIs(value["ready_to_run"], False)
                self.assertIsNone(session.decision["selected_calibrated_od_concentration"])
                self.assertNotIn("synthetic_selected_level", session.decision)
                self.assertEqual(session.decision["scientific_records"], 0)
        for invalid in (None, "REAL", "live", True, ["SYNTHETIC"]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                q.SelectionSession(evidence_kind=invalid)

    def test_mixed_pair_origin_or_version_fails_without_false_synthetic_label(self):
        n0, d0 = record(), record("D0")
        for change in ({"evidence_kind": "LIVE"}, {"evidence_kind": None},
                       {"schema_version": 1}):
            with self.subTest(change=change):
                result = q.qualify_pair(n0, {**d0, **change}, references=REFERENCES)
                self.assertEqual(result["stop_status"], "FAIL")
                self.assertFalse(result["qualification_evaluated"])
                self.assertIsNone(result["evidence_kind"])

    def test_mixed_session_origins_rejected_without_accepting_records(self):
        incoming = pairs("C1")
        incoming[0][1]["evidence_kind"] = "LIVE"
        session = q.SelectionSession(references=REFERENCES)
        before = session.to_record()
        with self.assertRaises(ValueError):
            session.add_level("C1", incoming)
        self.assertEqual(session.to_record(), before)
        with self.assertRaises(ValueError):
            q.SelectionSession(evidence_kind="LIVE", references=REFERENCES).add_level("C1", pairs("C1"))

    def test_mixed_repeat_origin_rejected_without_accepting_repeat(self):
        session = q.SelectionSession(references=REFERENCES)
        session.add_level("C1", pairs("C1"))
        before = session.to_record()
        n0, d0 = record("N0-CAL-R"), record("D0-CAL-R")
        d0["evidence_kind"] = "LIVE"
        with self.assertRaises(ValueError):
            session.add_repeats(n0, d0)
        self.assertEqual(session.to_record(), before)

    def test_selection_replay_rejects_origin_substitution(self):
        session = q.SelectionSession(references=REFERENCES)
        session.add_level("C1", pairs("C1"))
        original = session.to_record()
        self.assertEqual(q.validate_selection_record(original, references=REFERENCES), session.decision)
        for target in ("envelope", "decision", "run"):
            with self.subTest(target=target):
                changed = copy.deepcopy(original)
                if target == "envelope":
                    changed["evidence_kind"] = "LIVE"
                elif target == "decision":
                    changed["decision"]["evidence_kind"] = "LIVE"
                else:
                    changed["levels"][0]["pairs"][0]["N0"]["evidence_kind"] = "LIVE"
                with self.assertRaises(ValueError):
                    q.validate_selection_record(changed, references=REFERENCES)


if __name__ == "__main__":
    unittest.main()
