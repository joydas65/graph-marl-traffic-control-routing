"""Public-only protocol bindings and all twelve reconstructed input readbacks."""

import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.b0.od_concentration_v2 import od_input
from b0_od_v2_fixtures import CONTRACT_PATH, FROZEN_INPUT_SHA256, ROOT


class PublicProjectionTests(unittest.TestCase):
    def test_all_twelve_reconstructed_inputs_match_frozen_bytes_and_read_back(self):
        contract = od_input.load_contract(CONTRACT_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            for seed in contract["calibration_seeds"]:
                for level, trips in od_input.build_seed_allocations(contract, seed).items():
                    with self.subTest(seed=seed, level=level):
                        payload = od_input.serialize_routes(contract, seed, level, trips) + b"\n"
                        path = Path(temporary) / f"seed-{seed}-{level}.rou.xml"
                        path.write_bytes(payload)
                        readback = path.read_bytes()
                        self.assertEqual(readback, payload)
                        self.assertEqual(hashlib.sha256(readback).hexdigest(),
                                         FROZEN_INPUT_SHA256[f"{seed}-{level}"])
                        report = od_input.validate_routes_xml(contract, seed, level, readback)
                        self.assertEqual(report["scheduled_trips"], 540)
                        expected = next(item for item in contract["offline_validation"]["seed_reference_vectors"]
                                        if item["seed"] == seed)
                        self.assertEqual(report["logical_assignment_sha256"],
                                         expected["new_logical_assignment_sha256"][level])

    def test_unchanged_scientific_contract_and_public_dependency_bindings(self):
        contract = od_input.load_contract(CONTRACT_PATH)
        self.assertEqual(contract["contract_identity"], "B0_OD_CONCENTRATION_CALIBRATION_CONTRACT_V1")
        self.assertFalse(contract["ready_to_run"])
        self.assertIsNone(contract["authoritative_research_state"]["dissertation_delta"])
        self.assertEqual(contract["future_execution_budget"]["currently_authorized_simulations"], 0)
        for name, binding in contract["source_bindings"].items():
            if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
                with self.subTest(binding=name):
                    self.assertEqual(hashlib.sha256((ROOT / binding["path"]).read_bytes()).hexdigest(),
                                     binding["sha256"])


if __name__ == "__main__":
    unittest.main()
