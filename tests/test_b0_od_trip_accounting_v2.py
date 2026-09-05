"""Independent synthetic accounting oracles; no simulator or external inputs."""

from __future__ import annotations

import copy
import unittest

from scripts.b0.od_concentration_v2.cutoff_measurement import account_trips, completion_gate, parse_tripinfo_xml


HORIZON = 1500


def fixture() -> tuple[list[dict], dict]:
    """Hand-computable, distinct arrived/active/pending terminal observations."""
    scheduled = [
        {"vehicle_id": "a", "route_id": "row1_east", "scheduled_departure_seconds": 0},
        {"vehicle_id": "b", "route_id": "row0_west", "scheduled_departure_seconds": 20},
        {"vehicle_id": "c", "route_id": "colA_north", "scheduled_departure_seconds": 40},
        {"vehicle_id": "d", "route_id": "colC_south", "scheduled_departure_seconds": 60},
    ]
    records = [
        {"id": "a", "depart": "10", "arrival": "100", "waitingTime": "5"},
        {"id": "b", "depart": "30", "arrival": "-1", "waitingTime": "7"},
        {"id": "c", "depart": "-1", "arrival": "-1", "waitingTime": "0"},
        {"id": "d", "depart": "65", "arrival": "160", "waitingTime": "3"},
    ]
    parameters = {
        "tripinfo_records": records,
        "departed_events": {"a": [10], "b": [30], "d": [65]},
        "arrival_events": {"a": [100], "d": [160]},
        "cutoff_active_ids": {"b"},
        "cutoff_pending_ids": {"c"},
        "per_trip_halting_seconds": {"a": 1, "b": 2, "c": 0, "d": 0},
        "queue_trace": [[t, 1 if t == 10 else 2 if t == 30 else 0] for t in range(1, 1501)],
        "observations_complete": True,
        "final_time_seconds": HORIZON,
    }
    return scheduled, parameters


class TripinfoParsingTests(unittest.TestCase):
    def test_xml_preserves_raw_timestamp_waiting_and_extra_attributes(self) -> None:
        xml = b'<tripinfos><tripinfo id="u" depart="-1" arrival="-1" waitingTime="0" duration="-1" custom="kept"/></tripinfos>'
        records = parse_tripinfo_xml(xml)
        self.assertEqual(records, [{"id": "u", "depart": "-1", "arrival": "-1", "waitingTime": "0", "duration": "-1", "custom": "kept"}])

    def test_text_and_bytes_xml_have_identical_structured_records(self) -> None:
        xml = '<tripinfos><tripinfo id="a" depart="1" arrival="8" waitingTime="2.5"/></tripinfos>'
        self.assertEqual(parse_tripinfo_xml(xml), parse_tripinfo_xml(xml.encode("utf-8")))

    def test_duplicate_xml_ids_rejected_during_parsing(self) -> None:
        with self.assertRaises(ValueError):
            parse_tripinfo_xml('<tripinfos><tripinfo id="a" depart="10" arrival="100" waitingTime="5"/><tripinfo id="a" depart="10" arrival="100" waitingTime="5"/></tripinfos>')


class AllScheduledAccountingTests(unittest.TestCase):
    def test_synthetic_xml_records_feed_the_complete_accounting_adapter(self):
        scheduled, parameters = fixture()
        parameters["tripinfo_records"] = parse_tripinfo_xml(
            '<tripinfos><tripinfo id="a" depart="10" arrival="100" waitingTime="5"/>'
            '<tripinfo id="b" depart="30" arrival="-1" waitingTime="7"/>'
            '<tripinfo id="c" depart="-1" arrival="-1" waitingTime="0"/>'
            '<tripinfo id="d" depart="65" arrival="160" waitingTime="3"/></tripinfos>')
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "VALID")
        self.assertEqual(result["metrics"]["restricted_mean_trip_time_seconds"], 785)
        self.assertEqual(result["metrics"]["sumo_tripinfo_waiting_time_seconds_total"], 15)

    def test_mixed_population_has_independent_mean_p95_and_waiting_oracles(self) -> None:
        scheduled, parameters = fixture()
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "VALID")
        self.assertEqual(result["integrity_errors"], [])
        self.assertEqual(result["evidence_deficiencies"], [])
        metrics = result["metrics"]
        self.assertEqual(metrics["restricted_mean_trip_time_seconds"], 785)
        self.assertEqual(metrics["restricted_p95_trip_time_seconds_nearest_rank"], 1480)
        self.assertEqual(metrics["scheduled_trips"], 4)
        self.assertEqual(metrics["arrived_trips"], 2)
        self.assertEqual(metrics["unfinished_trips"], 2)
        self.assertEqual(metrics["completion_fraction"], 0.5)
        self.assertEqual(metrics["sumo_tripinfo_waiting_time_seconds_total"], 15)
        self.assertEqual(metrics["cumulative_queue_vehicle_seconds"], 3)
        self.assertEqual({key: value["restricted_trip_time_seconds"] for key, value in result["ledger"].items()}, {"a": 100, "b": 1480, "c": 1460, "d": 100})
        self.assertEqual({key: value["terminal_category"] for key, value in result["ledger"].items()}, {"a": "arrived", "b": "active", "c": "not_departed", "d": "arrived"})

    def test_all_540_arrived_remain_in_denominator(self) -> None:
        scheduled = []
        records = []
        departures = {}
        arrivals = {}
        for index in range(540):
            b, k = divmod(index, 36)
            t = 60 * b + (5 * k) // 3
            vehicle_id = f"veh_{index:04d}"
            scheduled.append({"vehicle_id": vehicle_id, "route_id": "row1_east", "scheduled_departure_seconds": t})
            records.append({"id": vehicle_id, "depart": t + 1, "arrival": t + 101, "waitingTime": 1})
            departures[vehicle_id] = [t + 1]
            arrivals[vehicle_id] = [t + 101]
        result = account_trips(scheduled, tripinfo_records=records, departed_events=departures, arrival_events=arrivals, cutoff_active_ids=set(), cutoff_pending_ids=set(), per_trip_halting_seconds={item["vehicle_id"]: 0 for item in scheduled}, queue_trace=[[t, 0] for t in range(1, 1501)])
        self.assertEqual(result["measurement_status"], "VALID")
        self.assertEqual(len(result["ledger"]), 540)
        self.assertEqual(result["metrics"]["scheduled_trips"], 540)
        self.assertEqual(result["metrics"]["arrived_trips"], 540)
        self.assertEqual(result["metrics"]["unfinished_trips"], 0)
        self.assertEqual(result["metrics"]["restricted_mean_trip_time_seconds"], 101)
        self.assertEqual(result["metrics"]["restricted_p95_trip_time_seconds_nearest_rank"], 101)
        self.assertEqual(result["metrics"]["sumo_tripinfo_waiting_time_seconds_total"], 540)

    def test_active_trip_retains_raw_negative_arrival_and_cutoff_endpoint(self) -> None:
        scheduled, parameters = fixture()
        result = account_trips(scheduled, **parameters)
        active = result["ledger"]["b"]
        self.assertEqual(active["terminal_category"], "active")
        self.assertEqual(active["raw_tripinfo"]["arrival"], "-1")
        self.assertIsNone(active["valid_non_teleported_arrival_seconds"])
        self.assertEqual(active["restricted_trip_time_seconds"], 1480)

    def test_departure_delay_native_waiting_queue_and_restricted_time_are_distinct(self) -> None:
        scheduled, parameters = fixture()
        result = account_trips(scheduled, **parameters)
        a = result["ledger"]["a"]
        self.assertEqual(a["departure_delay_seconds"], 10)
        self.assertEqual(a["native_waiting_normalized_seconds"], 5)
        self.assertEqual(a["restricted_trip_time_seconds"], 100)
        self.assertEqual(result["metrics"]["cumulative_queue_vehicle_seconds"], 3)
        self.assertNotEqual(result["metrics"]["cumulative_queue_vehicle_seconds"], result["metrics"]["sumo_tripinfo_waiting_time_seconds_total"])

    def test_inputs_are_not_mutated(self) -> None:
        scheduled, parameters = fixture()
        before = copy.deepcopy((scheduled, parameters))
        account_trips(scheduled, **parameters)
        self.assertEqual((scheduled, parameters), before)

    def test_arrival_at_cutoff_is_observed_arrival_not_invented_censoring(self) -> None:
        scheduled, parameters = fixture()
        parameters["tripinfo_records"][1]["arrival"] = "1500"
        parameters["arrival_events"]["b"] = [1500]
        parameters["cutoff_active_ids"] = set()
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "VALID")
        self.assertEqual(result["ledger"]["b"]["terminal_category"], "arrived")
        self.assertEqual(result["ledger"]["b"]["valid_non_teleported_arrival_seconds"], 1500)
        self.assertEqual(result["metrics"]["arrived_trips"], 3)


class WaitingNormalizationTests(unittest.TestCase):
    def test_proven_undeparted_missing_tripinfo_has_zero_wait_but_full_burden(self) -> None:
        scheduled, parameters = fixture()
        parameters["tripinfo_records"] = [r for r in parameters["tripinfo_records"] if r["id"] != "c"]
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "VALID")
        self.assertEqual(result["ledger"]["c"]["native_waiting_normalized_seconds"], 0)
        self.assertEqual(result["ledger"]["c"]["restricted_trip_time_seconds"], 1460)
        self.assertIsNone(result["ledger"]["c"]["valid_non_teleported_arrival_seconds"])
        self.assertEqual(result["metrics"]["sumo_tripinfo_waiting_time_seconds_total"], 15)

    def test_proven_undeparted_missing_or_null_waiting_is_zero(self) -> None:
        for form in ("missing", "null", "zero"):
            with self.subTest(form=form):
                scheduled, parameters = fixture()
                record = parameters["tripinfo_records"][2]
                if form == "missing":
                    del record["waitingTime"]
                elif form == "null":
                    record["waitingTime"] = None
                result = account_trips(scheduled, **parameters)
                self.assertEqual(result["measurement_status"], "VALID")
                self.assertEqual(result["ledger"]["c"]["native_waiting_normalized_seconds"], 0)

    def test_proven_undeparted_positive_native_wait_is_a_contradiction(self) -> None:
        scheduled, parameters = fixture()
        parameters["tripinfo_records"][2]["waitingTime"] = "1"
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")
        self.assertTrue(result["integrity_errors"])

    def test_negative_undeparted_wait_is_not_assumed_to_be_a_documented_sentinel(self) -> None:
        scheduled, parameters = fixture()
        parameters["tripinfo_records"][2]["waitingTime"] = "-1"
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "EVIDENCE_DEFICIENCY")
        self.assertEqual(result["ledger"]["c"]["raw_tripinfo"]["waitingTime"], "-1")
        self.assertIsNone(result["metrics"]["sumo_tripinfo_waiting_time_seconds_total"])
        self.assertEqual(result["ledger"]["c"]["restricted_trip_time_seconds"], 1460)

    def test_departed_missing_waiting_does_not_become_zero(self) -> None:
        for vehicle_index in (0, 1):
            with self.subTest(vehicle_index=vehicle_index):
                scheduled, parameters = fixture()
                del parameters["tripinfo_records"][vehicle_index]["waitingTime"]
                result = account_trips(scheduled, **parameters)
                self.assertEqual(result["measurement_status"], "EVIDENCE_DEFICIENCY")
                self.assertTrue(result["evidence_deficiencies"])
                self.assertIsNone(result["metrics"]["sumo_tripinfo_waiting_time_seconds_total"])

    def test_departed_invalid_waiting_does_not_produce_negative_or_false_zero_total(self) -> None:
        for value in (-1, "-0.1", None, "nan", "inf", "not-a-number"):
            with self.subTest(value=value):
                scheduled, parameters = fixture()
                parameters["tripinfo_records"][1]["waitingTime"] = value
                result = account_trips(scheduled, **parameters)
                self.assertEqual(result["measurement_status"], "EVIDENCE_DEFICIENCY")
                self.assertIsNone(result["metrics"]["sumo_tripinfo_waiting_time_seconds_total"])
                self.assertEqual(result["metrics"]["restricted_mean_trip_time_seconds"], 785)

    def test_missing_active_tripinfo_does_not_reclassify_vehicle_as_never_departed(self) -> None:
        scheduled, parameters = fixture()
        parameters["tripinfo_records"] = [r for r in parameters["tripinfo_records"] if r["id"] != "b"]
        result = account_trips(scheduled, **parameters)
        self.assertNotEqual(result["measurement_status"], "VALID")
        self.assertEqual(result["ledger"]["b"]["terminal_category"], "active")
        self.assertEqual(result["ledger"]["b"]["restricted_trip_time_seconds"], 1480)
        self.assertIsNone(result["metrics"]["sumo_tripinfo_waiting_time_seconds_total"])


class AccountingIntegrityTests(unittest.TestCase):
    def test_fractional_or_zero_observation_endpoint_is_invalid(self):
        for endpoint in (0, 10.5):
            scheduled, parameters = fixture()
            parameters["departed_events"]["a"] = [endpoint]
            self.assertEqual(account_trips(scheduled, **parameters)["measurement_status"], "INTEGRITY_FAILURE")

    def test_halting_cannot_exceed_a_late_departed_sampled_lifetime(self):
        scheduled = [{"vehicle_id": "a", "route_id": "row1_east", "scheduled_departure_seconds": 898}]
        result = account_trips(scheduled,
            tripinfo_records=[{"id": "a", "depart": 1499, "arrival": -1, "waitingTime": 0}],
            departed_events={"a": [1499]}, arrival_events={},
            cutoff_active_ids=["a"], cutoff_pending_ids=[],
            per_trip_halting_seconds={"a": 1500}, queue_trace=[[t, 1] for t in range(1, 1501)])
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")

    def test_queue_cannot_appear_before_any_observed_departure(self):
        scheduled, parameters = fixture()
        parameters["queue_trace"][0][1] = 1
        parameters["queue_trace"][9][1] = 0
        self.assertEqual(account_trips(scheduled, **parameters)["measurement_status"], "INTEGRITY_FAILURE")

    def test_duplicate_scheduled_id_rejected(self) -> None:
        scheduled, parameters = fixture()
        scheduled.append(copy.deepcopy(scheduled[0]))
        with self.assertRaises(ValueError):
            account_trips(scheduled, **parameters)

    def test_duplicate_tripinfo_id_rejected(self) -> None:
        scheduled, parameters = fixture()
        parameters["tripinfo_records"].append(copy.deepcopy(parameters["tripinfo_records"][0]))
        with self.assertRaises(ValueError):
            account_trips(scheduled, **parameters)

    def test_unknown_tripinfo_id_is_integrity_failure(self) -> None:
        scheduled, parameters = fixture()
        parameters["tripinfo_records"].append({"id": "unknown", "depart": -1, "arrival": -1, "waitingTime": 0})
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")

    def test_unknown_observed_id_is_integrity_failure(self) -> None:
        scheduled, parameters = fixture()
        parameters["departed_events"]["unknown"] = [2]
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")

    def test_duplicate_departure_event_is_integrity_failure(self) -> None:
        scheduled, parameters = fixture()
        parameters["departed_events"]["a"] = [10, 11]
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")

    def test_missing_record_and_pending_proof_is_unexplained_not_zero_exposure(self) -> None:
        scheduled, parameters = fixture()
        parameters["tripinfo_records"] = [r for r in parameters["tripinfo_records"] if r["id"] != "c"]
        parameters["cutoff_pending_ids"] = set()
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")
        self.assertNotEqual(result["ledger"]["c"]["terminal_category"], "not_departed")

    def test_active_and_pending_identity_overlap_is_not_hidden_by_category_priority(self) -> None:
        scheduled, parameters = fixture()
        parameters["cutoff_pending_ids"].add("b")
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")

    def test_arrived_and_active_overlap_is_integrity_failure(self) -> None:
        scheduled, parameters = fixture()
        parameters["cutoff_active_ids"].add("a")
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")

    def test_observed_arrival_without_departure_evidence_is_not_trustworthy(self) -> None:
        scheduled, parameters = fixture()
        del parameters["departed_events"]["a"]
        result = account_trips(scheduled, **parameters)
        self.assertNotEqual(result["measurement_status"], "VALID")

    def test_arrival_before_departure_is_integrity_failure(self) -> None:
        scheduled, parameters = fixture()
        parameters["tripinfo_records"][0]["arrival"] = "9"
        parameters["arrival_events"]["a"] = [9]
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")

    def test_departure_before_schedule_is_integrity_failure(self) -> None:
        scheduled, parameters = fixture()
        parameters["tripinfo_records"][1]["depart"] = "19"
        parameters["departed_events"]["b"] = [19]
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")

    def test_teleport_is_not_ordinary_censoring(self) -> None:
        scheduled, parameters = fixture()
        parameters["teleport_start_events"] = {"b": [100]}
        parameters["teleport_end_events"] = {"b": [101]}
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")
        self.assertEqual(result["ledger"]["b"]["terminal_category"], "teleported")
        self.assertIsNone(result["ledger"]["b"]["valid_non_teleported_arrival_seconds"])

    def test_missing_queue_step_is_not_an_ordinary_unfinished_trip(self) -> None:
        scheduled, parameters = fixture()
        parameters["queue_trace"].pop(20)
        result = account_trips(scheduled, **parameters)
        self.assertNotEqual(result["measurement_status"], "VALID")

    def test_duplicate_queue_timestamp_is_not_silently_collapsed(self) -> None:
        scheduled, parameters = fixture()
        parameters["queue_trace"].append(parameters["queue_trace"][10].copy())
        result = account_trips(scheduled, **parameters)
        self.assertNotEqual(result["measurement_status"], "VALID")

    def test_incomplete_observation_flag_cannot_prove_never_departed(self) -> None:
        scheduled, parameters = fixture()
        parameters["observations_complete"] = False
        result = account_trips(scheduled, **parameters)
        self.assertNotEqual(result["measurement_status"], "VALID")

    def test_early_final_time_is_not_relabelled_as_frozen_cutoff(self) -> None:
        scheduled, parameters = fixture()
        parameters["final_time_seconds"] = 1499
        result = account_trips(scheduled, **parameters)
        self.assertNotEqual(result["measurement_status"], "VALID")

    def test_queue_and_per_trip_halting_mismatch_is_integrity_failure(self) -> None:
        scheduled, parameters = fixture()
        parameters["per_trip_halting_seconds"]["b"] = 3
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")

    def test_missing_scheduled_halting_identity_is_integrity_failure(self) -> None:
        scheduled, parameters = fixture()
        del parameters["per_trip_halting_seconds"]["c"]
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "INTEGRITY_FAILURE")


class ExactCompletionGateTests(unittest.TestCase):
    def test_n0_exact_540_integer_boundary(self) -> None:
        self.assertTrue(completion_gate(535, 540, condition="N0"))
        self.assertFalse(completion_gate(534, 540, condition="N0"))

    def test_d0_exact_540_integer_boundary(self) -> None:
        self.assertTrue(completion_gate(513, 540, condition="D0"))
        self.assertFalse(completion_gate(512, 540, condition="D0"))

    def test_trustworthy_unfinished_measurement_can_fail_completion(self) -> None:
        scheduled, parameters = fixture()
        result = account_trips(scheduled, **parameters)
        self.assertEqual(result["measurement_status"], "VALID")
        self.assertFalse(completion_gate(result["metrics"]["arrived_trips"], result["metrics"]["scheduled_trips"], condition="N0"))

    def test_invalid_denominator_or_condition_is_not_a_scientific_failure(self) -> None:
        for count, total, condition in ((0, 0, "N0"), (-1, 540, "D0"), (541, 540, "N0"), (535, 540, "X")):
            with self.subTest(count=count, total=total, condition=condition):
                with self.assertRaises(ValueError):
                    completion_gate(count, total, condition=condition)


if __name__ == "__main__":
    unittest.main()
