"""Publication-only identity, import-location and resource-limit checks."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.b0.od_integration_v1 import evidence, integration, qualification, finalization


ROOT = Path(__file__).resolve().parents[1]


class PublicIntegrationProjectionTests(unittest.TestCase):
    def test_public_source_identities_and_import_locations(self):
        manifest = json.loads((ROOT / "tests/reference/b0_od_integration_v1_projection.json").read_text())
        self.assertEqual(manifest["integration_identity"], "B0_OD_INTEGRATION_LAYER_V1")
        for entry in manifest["files"]:
            with self.subTest(public_path=entry["public_path"]):
                self.assertEqual(hashlib.sha256((ROOT / entry["public_path"]).read_bytes()).hexdigest(),
                                 entry["public_sha256"])
        self.assertEqual(manifest["status_correction"]["reviewed_public_head"],
                         "e635d14ec50a11ba502829708630446caf6d65b2")
        for entry in manifest["files"]:
            self.assertIn("initial_publication_sha256", entry)
            if entry["public_path"].endswith(("/integration.py", "/qualification.py", "/evidence.py")):
                self.assertNotEqual(entry["public_sha256"], entry["initial_publication_sha256"])
                self.assertIn("operational", entry["adjustment"].lower())
        for path, expected in manifest["additional_public_test_sha256"].items():
            with self.subTest(additional_public_test=path):
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)
        for path, expected in manifest["finalization_extension"]["current_additions_sha256"].items():
            with self.subTest(current_addition=path):
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)
        for path, expected in manifest['thin_binding']['current_source_test_sha256'].items():
            with self.subTest(thin_binding_identity=path):
                self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), expected)
        self.assertEqual(manifest['thin_binding']['native_factory_status'], 'IMPLEMENTED_OFFLINE_ONLY')
        self.assertEqual(manifest['native_factory']['prior_status'], 'UNRESOLVED_BOUNDED_ACQUISITION')
        self.assertFalse(manifest['native_factory']['native_process_test_executed'])
        self.assertFalse(manifest['native_factory']['pre_bootstrap_hard_deadline_claimed'])
        self.assertTrue(manifest['native_factory']['requires_exclusive_worker_reaping'])
        cleanup = manifest['terminal_cleanup_correction']
        self.assertEqual(cleanup['accepted_base'], '215ff23487df71fc1fa4d701e7e7959c43a9cf70')
        self.assertEqual(cleanup['historical_results'], {'original_P2': 'FAIL', 'diagnostic_P2': 'FAIL'})
        self.assertFalse(cleanup['native_revalidation_executed'])
        self.assertFalse(cleanup['exact_native_denial_cause_proven'])
        self.assertFalse(cleanup['ready_to_run'])
        for path in ('scripts/b0/od_integration_v1/native_supervisor.py',
                     'scripts/b0/od_integration_v1/native_worker.py'):
            with self.subTest(terminal_cleanup_source=path):
                self.assertEqual(cleanup['prior_source_test_sha256'][path],
                                 manifest['publication_checkpoint']['reviewed_source_test_sha256'][path])
                self.assertNotEqual(cleanup['prior_source_test_sha256'][path],
                                    manifest['thin_binding']['current_source_test_sha256'][path])
        self.assertIn('tests/test_b0_od_integration_terminal_cleanup.py',
                      manifest['thin_binding']['current_source_test_sha256'])
        correction = manifest['inconclusive_handoff_correction']
        self.assertEqual(correction['reviewed_head'],
                         '7e1733ad11f2b240f80c942a79fb91c6799c2024')
        self.assertEqual(correction['reviewed_tree'],
                         '3d53dcebcf7cc06f85aa858fa06f3401add6c99c')
        self.assertEqual(correction['prior_validation']['integration'],
                         {'tests': 361, 'subtests': 536})
        self.assertEqual(correction['prior_validation']['existing'],
                         {'tests': 153, 'subtests': 175})
        self.assertFalse(correction['native_revalidation_executed'])
        prior = correction['prior_source_test_sha256']
        current = manifest['thin_binding']['current_source_test_sha256']
        self.assertEqual(prior['scripts/b0/od_integration_v1/native_worker.py'],
                         'd6504c1b2c13ecc7fb297561844b9732d6a649ab41838f7842c336472d545b64')
        self.assertNotEqual(prior['scripts/b0/od_integration_v1/native_worker.py'],
                            current['scripts/b0/od_integration_v1/native_worker.py'])
        for path in prior:
            if path.startswith('scripts/') and not path.endswith('/native_worker.py'):
                with self.subTest(unchanged_inconclusive_dependency=path):
                    self.assertEqual(prior[path], current[path])
        self.assertIn('tests/test_b0_od_integration_inconclusive_handoff.py', current)
        publication = manifest['publication_checkpoint']
        self.assertEqual(publication['reviewed_archive_sha256'],
                         '75a52955f7d01fe2ebb30ae4b2a288d465209823a059ebdab71d3c7215e58481')
        editorial = publication['editorial_adjustment']
        self.assertEqual(editorial['path'], 'scripts/b0/od_integration_v1/finalization.py')
        self.assertEqual(editorial['kind'], 'OPENING_DOCSTRING_ONLY')
        self.assertEqual(publication['reviewed_source_test_sha256'][editorial['path']],
                         '990a2faf8ddd0029fd644e13101e1958eba50ed50c1486cd1b77d3ca6e5b2d86')
        self.assertNotEqual(publication['reviewed_source_test_sha256'][editorial['path']],
                            manifest['thin_binding']['current_source_test_sha256'][editorial['path']])
        self.assertEqual(manifest["accepted_checkpoint"]["revision"], integration.LEGACY_REVISION)
        self.assertEqual(manifest["accepted_checkpoint"]["implementation_sha256"], integration.LEGACY_SOURCE_SHA256)
        for entry in manifest["files"]:
            self.assertIn("accepted_checkpoint_sha256", entry)
        for path, expected in manifest["finalization_extension"]["preserved_characterization_sha256"].items():
            with self.subTest(preserved_characterization=path):
                self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), expected)
        for path, expected in manifest["accepted_dependency_sha256"].items():
            with self.subTest(frozen_dependency=path):
                self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), expected)
        for module in (integration, qualification, evidence, finalization):
            self.assertEqual(Path(module.__file__).resolve().parent,
                             ROOT / "scripts/b0/od_integration_v1")
        self.assertEqual(evidence.WORKSPACE,
                         ROOT / ".local-evidence/b0-od-integration-public-v1")

    def test_oversize_json_is_rejected_without_completed_record(self):
        self.assertEqual(evidence.MAX_BYTES, 64 * 1024 * 1024)
        output = evidence.WORKSPACE / "synthetic-test-outputs"
        output.mkdir(parents=True, exist_ok=True)
        payload = {**evidence.PAYLOAD_BASE, "record_kind": "FAILURE", "record": {
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
