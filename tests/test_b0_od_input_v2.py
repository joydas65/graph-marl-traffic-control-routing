"""Offline OD fixtures; expectations come from the frozen table and source XML."""

from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

HERE = Path(__file__).parent
from scripts.b0.od_concentration_v2 import od_input


# Independently transcribed from the frozen design table, canonical route order.
EXPECTED_COUNTS = {
    "C1": [41, 41, 90, 41, 41, 41, 41, 41, 41, 41, 41, 40],
    "C2": [37, 37, 135, 37, 37, 37, 37, 37, 37, 37, 36, 36],
    "C3": [33, 33, 180, 33, 33, 33, 33, 33, 33, 32, 32, 32],
    "C4": [25, 25, 270, 25, 25, 25, 25, 24, 24, 24, 24, 24],
}
BLOCK_TARGETS = {"C1": 6, "C2": 9, "C3": 12, "C4": 18}


class ODInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_path = HERE.parent / "configs/b0/od-concentration-v1/calibration-contract.json"
        cls.contract = od_input.load_contract(cls.contract_path)
        cls.by_seed = {
            seed: od_input.build_seed_allocations(cls.contract, seed)
            for seed in (20260904, 20260905, 20260906)
        }

    def test_all_twelve_allocations_against_independent_table_and_digests(self):
        route_order = self.contract["allocation"]["canonical_route_order"]
        for seed, allocations in self.by_seed.items():
            oracle = next(r for r in self.contract["offline_validation"]["seed_reference_vectors"]
                          if r["seed"] == seed)
            for level, trips in allocations.items():
                with self.subTest(seed=seed, level=level):
                    self.assertEqual(len(trips), 540)
                    self.assertEqual(len({t.vehicle_id for t in trips}), 540)
                    self.assertEqual([t.vehicle_id for t in trips], [f"veh_{i:04d}" for i in range(540)])
                    # Equivalent frozen 3X construction, independently expressed by index.
                    self.assertEqual([t.scheduled_departure_seconds for t in trips],
                                     [(i // 36) * 60 + ((i % 36) * 60) // 36 for i in range(540)])
                    counts = Counter(t.route_id for t in trips)
                    self.assertEqual([counts[r] for r in route_order], EXPECTED_COUNTS[level])
                    for start in range(0, 540, 36):
                        block = Counter(t.route_id for t in trips[start:start + 36])
                        self.assertEqual(set(block), set(route_order))
                        self.assertEqual(block["row1_east"], BLOCK_TARGETS[level])
                        residual = [n for r, n in block.items() if r != "row1_east"]
                        self.assertLessEqual(max(residual) - min(residual), 1)
                    rows = [[t.vehicle_id, t.scheduled_departure_seconds, t.route_id] for t in trips]
                    digest = hashlib.sha256(json.dumps(rows, ensure_ascii=True,
                                                      separators=(",", ":")).encode()).hexdigest()
                    self.assertEqual(digest, oracle["new_logical_assignment_sha256"][level])

    def test_nested_target_sets_and_deterministic_regeneration(self):
        for seed, allocations in self.by_seed.items():
            self.assertEqual(od_input.build_seed_allocations(self.contract, seed), allocations)
            prior = set()
            for level in ("C1", "C2", "C3", "C4"):
                target = {t.vehicle_id for t in allocations[level] if t.route_id == "row1_east"}
                self.assertLess(prior, target)
                prior = target
            self.assertNotEqual(allocations["C1"], allocations["C4"])

    def test_exactly_one_local_rng_and_fifteen_fresh_shuffles(self):
        instances = []
        original_random = random.Random

        class TrackingRandom(original_random):
            def __init__(self, seed):
                super().__init__(seed)
                self.shuffled_lists = []
                instances.append(self)

            def shuffle(self, values):
                self.assert_fresh = values == list(range(36))
                if not self.assert_fresh or any(values is old for old in self.shuffled_lists):
                    raise AssertionError("shuffle did not receive a fresh canonical slot list")
                self.shuffled_lists.append(values)
                return super().shuffle(values)

        global_state = random.getstate()
        with patch.object(od_input.random, "Random", TrackingRandom):
            od_input.build_seed_allocations(self.contract, 20260904)
        self.assertEqual(len(instances), 1)
        self.assertEqual(len(instances[0].shuffled_lists), 15)
        self.assertEqual(random.getstate(), global_state)

    def test_xml_geometry_and_attributes_match_frozen_public_source(self):
        binding = self.contract["source_bindings"]["original_routes"]
        source = (HERE.parent / binding["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), binding["sha256"])
        frozen = ET.fromstring(source)
        expected_routes = [node.attrib for node in frozen.findall("route")]
        expected_type = frozen.find("vType").attrib
        for seed, allocations in self.by_seed.items():
            for level, trips in allocations.items():
                with self.subTest(seed=seed, level=level):
                    raw = od_input.serialize_routes(self.contract, seed, level, trips)
                    self.assertEqual(raw, od_input.serialize_routes(self.contract, seed, level, trips))
                    report = od_input.validate_routes_xml(self.contract, seed, level, raw)
                    root = ET.fromstring(raw)
                    self.assertEqual([n.attrib for n in root.findall("route")], expected_routes)
                    self.assertEqual(root.find("vType").attrib, expected_type)
                    for node in root.findall("vehicle"):
                        self.assertEqual(set(node.attrib), {"id", "type", "route", "depart", "departLane", "departSpeed"})
                        self.assertEqual(node.attrib["type"], "passenger_deterministic")
                        self.assertEqual(node.attrib["departLane"], "best")
                        self.assertEqual(node.attrib["departSpeed"], "max")
                    self.assertEqual(report["xml_sha256"], hashlib.sha256(raw).hexdigest())
                    pair = od_input.paired_inputs(self.contract, seed, level, trips)
                    self.assertIs(pair["N0"], pair["D0"])
                    self.assertEqual(pair["N0"], raw)

    def test_serialization_only_difference_does_not_change_logical_assignment(self):
        trips = self.by_seed[20260904]["C1"]
        raw = od_input.serialize_routes(self.contract, 20260904, "C1", trips)
        different_whitespace = raw.replace(b"\n  ", b"\n    ")
        a = od_input.validate_routes_xml(self.contract, 20260904, "C1", raw)
        b = od_input.validate_routes_xml(self.contract, 20260904, "C1", different_whitespace)
        self.assertNotEqual(a["xml_sha256"], b["xml_sha256"])
        self.assertEqual(a["logical_assignment_sha256"], b["logical_assignment_sha256"])

    def test_seed_and_level_boundaries(self):
        for seed in (None, True, 20260904.0, 20260903, "20260904"):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                od_input.build_seed_allocations(self.contract, seed)
        trips = self.by_seed[20260904]["C1"]
        for level in (None, 1, "c1", "C0", "C5", "3X"):
            with self.subTest(level=level), self.assertRaises(ValueError):
                od_input.serialize_routes(self.contract, 20260904, level, trips)

    def test_reject_changed_contract_or_unbound_file_bytes(self):
        altered = deepcopy(self.contract)
        altered["qualification_contract"]["d0_mean_trip_time_increase_seconds_minimum"] = 0
        with self.assertRaises(ValueError):
            od_input.build_seed_allocations(altered, 20260904)
        with patch.object(Path, "read_bytes", return_value=b"{}"):
            with self.assertRaises(ValueError):
                od_input.load_contract(self.contract_path)

    def test_reject_wrong_count_id_order_departure_and_assignment(self):
        base = self.by_seed[20260904]["C1"]
        mutations = {
            "count": base[:-1],
            "id": (replace(base[0], vehicle_id="veh_0001"),) + base[1:],
            "order": (base[1], base[0]) + base[2:],
            "departure": (replace(base[0], scheduled_departure_seconds=1),) + base[1:],
            "departure_type": (replace(base[0], scheduled_departure_seconds=False),) + base[1:],
            "unknown_route": (replace(base[0], route_id="new_route"),) + base[1:],
        }
        # Swap two non-target route labels in one block: counts remain right, digest must fail.
        left = next(i for i in range(36) if base[i].route_id != "row1_east")
        right = next(i for i in range(36) if base[i].route_id not in {"row1_east", base[left].route_id})
        swapped = list(base)
        swapped[left] = replace(base[left], route_id=base[right].route_id)
        swapped[right] = replace(base[right], route_id=base[left].route_id)
        mutations["assignment_despite_correct_counts"] = swapped
        for name, trips in mutations.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                od_input.validate_allocation(self.contract, 20260904, "C1", trips)

    def test_reject_xml_drift_and_rerouting(self):
        raw = od_input.serialize_routes(self.contract, 20260904, "C1", self.by_seed[20260904]["C1"])
        for case in ("geometry", "route_order", "extra_attribute", "vehicle_behavior",
                     "nested_route", "missing_vehicle", "wrong_depart", "duplicate_id", "root_attribute"):
            root = ET.fromstring(raw)
            vehicle = root.find("vehicle")
            if case == "geometry": root.find("route").set("edges", "A1B1")
            elif case == "route_order":
                a, b = root[1], root[2]
                root[1], root[2] = b, a
            elif case == "extra_attribute": vehicle.set("reroute", "true")
            elif case == "vehicle_behavior": root.find("vType").set("sigma", "1")
            elif case == "nested_route": ET.SubElement(vehicle, "route", {"edges": "A1B1"})
            elif case == "missing_vehicle": root.remove(vehicle)
            elif case == "wrong_depart": vehicle.set("depart", "0.0")
            elif case == "duplicate_id": vehicle.set("id", "veh_0001")
            elif case == "root_attribute": root.set("unexpected", "1")
            with self.subTest(case=case), self.assertRaises(ValueError):
                od_input.validate_routes_xml(self.contract, 20260904, "C1", ET.tostring(root))


if __name__ == "__main__":
    unittest.main()
