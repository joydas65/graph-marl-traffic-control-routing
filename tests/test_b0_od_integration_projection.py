"""Publication-only identity, import-location and resource-limit checks."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.b0.od_integration_v1 import evidence, integration, qualification


ROOT = Path(__file__).resolve().parents[1]


class PublicIntegrationProjectionTests(unittest.TestCase):
    def test_public_source_identities_and_import_locations(self):
        manifest = json.loads((ROOT / "tests/reference/b0_od_integration_v1_projection.json").read_text())
        self.assertEqual(manifest["integration_identity"], "B0_OD_INTEGRATION_LAYER_V1")
        for entry in manifest["files"]:
            with self.subTest(public_path=entry["public_path"]):
                self.assertEqual(hashlib.sha256((ROOT / entry["public_path"]).read_bytes()).hexdigest(),
                                 entry["public_sha256"])
        for module in (integration, qualification, evidence):
            self.assertEqual(Path(module.__file__).resolve().parent,
                             ROOT / "scripts/b0/od_integration_v1")
        self.assertEqual(evidence.WORKSPACE,
                         ROOT / ".local-evidence/b0-od-integration-public-v1")

    def test_oversize_json_is_rejected_without_completed_record(self):
        self.assertEqual(evidence.MAX_BYTES, 64 * 1024 * 1024)
        output = evidence.WORKSPACE / "synthetic-test-outputs"
        output.mkdir(parents=True, exist_ok=True)
        payload = {**evidence.BASE, "record_kind": "FAILURE", "record": {
            "failure_code": "SYNTHETIC_SIZE_CHECK", "measurement_status": None,
            "run": None, "raw_evidence": "x" * evidence.MAX_BYTES}}
        with tempfile.TemporaryDirectory(dir=output) as temporary:
            destination = Path(temporary)
            with self.assertRaises(evidence.EvidenceError) as caught:
                evidence.write_once(destination, "oversize.json", payload)
            self.assertEqual(caught.exception.code, "PAYLOAD_SIZE_LIMIT")
            self.assertEqual(caught.exception.experiment_status, "FAIL")
            self.assertFalse((destination / "oversize.json").exists())
            self.assertFalse((destination / "oversize.json.complete.json").exists())
            self.assertFalse((destination / "oversize.json.pending").exists())
            self.assertIsNotNone(caught.exception.failure_receipt_name)
            receipt = json.loads((destination / caught.exception.failure_receipt_name).read_text())
            self.assertEqual(receipt["failure_code"], "PAYLOAD_SIZE_LIMIT")
            self.assertIs(receipt["completed"], False)


if __name__ == "__main__":
    unittest.main()
