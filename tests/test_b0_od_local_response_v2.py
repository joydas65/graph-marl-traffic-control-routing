"""Independent local witness fixtures; censored bounds never become point data."""
import copy
import unittest

from scripts.b0.od_concentration_v2.cutoff_measurement import (
    COMPLETED, OBSERVER_IDENTITY, RIGHT_CENSORED_AT_CUTOFF, paired_local_response,
)


def fixture():
    visit = {
        "vehicle_id": "a", "occurrence_index": 0,
        "edge_id": "A1B1", "entry_period": "DURING", "visit_status": COMPLETED,
        "entry_observed_at_seconds": 310,
        "entry_transition_interval_start_seconds": 309,
        "entry_transition_interval_end_seconds": 310,
        "exit_observed_at_seconds": 320,
        "exit_transition_interval_start_seconds": 319,
        "exit_transition_interval_end_seconds": 320,
        "observed_edge_time_seconds": 10, "observed_halting_seconds": 2,
    }
    summary = {
        "observer_identity": OBSERVER_IDENTITY, "cutoff_seconds": 1500,
        "exposure_observability_complete": True,
        "unique_edge_entries": {"during": ["a"]},
        "unique_edge_entry_counts": {"during": 1},
        "per_vehicle": {"a": {"edge_visits": [visit]}},
    }
    ledger = {"a": {
        "route_id": "row1_east", "scheduled_departure_seconds": 200,
        "terminal_category": "arrived", "valid_non_teleported_arrival_seconds": 400,
    }}
    return copy.deepcopy(summary), copy.deepcopy(summary), copy.deepcopy(ledger), copy.deepcopy(ledger)


def censor(summary, ledger, vehicle_id="a"):
    visit = summary["per_vehicle"][vehicle_id]["edge_visits"][0]
    visit.update(visit_status=RIGHT_CENSORED_AT_CUTOFF,
                 exit_observed_at_seconds=None, exit_transition_interval_start_seconds=None,
                 exit_transition_interval_end_seconds=None, cutoff_seconds=1500,
                 observed_edge_time_seconds=None, observed_followup_seconds=1190,
                 observed_duration_lower_bound_seconds=1190, observed_halting_seconds=900)
    ledger[vehicle_id].update(terminal_category="active", valid_non_teleported_arrival_seconds=None)


class LocalResponseTests(unittest.TestCase):
    def test_completed_equal_pair_is_identifiable_nonresponse(self):
        result = paired_local_response(*fixture())
        self.assertEqual(result["status"], "FAIL")
        self.assertIs(result["local_physical_response_observed"], False)
        self.assertEqual(result["comparisons"][0]["edge_time_delta_seconds"], 0)

    def test_each_completed_witness_channel_retains_existential_rule(self):
        for channel in ("edge_time", "halting", "arrival"):
            with self.subTest(channel=channel):
                n, d, nl, dl = fixture()
                if channel == "arrival":
                    dl["a"]["valid_non_teleported_arrival_seconds"] = 401
                else:
                    key = "observed_edge_time_seconds" if channel == "edge_time" else "observed_halting_seconds"
                    d["per_vehicle"]["a"]["edge_visits"][0][key] += 1
                    if channel == "edge_time":
                        for field in ("exit_observed_at_seconds", "exit_transition_interval_start_seconds", "exit_transition_interval_end_seconds"):
                            d["per_vehicle"]["a"]["edge_visits"][0][field] += 1
                result = paired_local_response(n, d, nl, dl)
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["vehicles_with_local_physical_response"], ["a"])

    def test_one_censored_visit_does_not_create_large_duration_or_halting_witness(self):
        n, d, nl, dl = fixture()
        censor(d, dl)
        result = paired_local_response(n, d, nl, dl)
        self.assertEqual(result["status"], "NOT_IDENTIFIABLE")
        comparison = result["comparisons"][0]
        self.assertIsNone(comparison["edge_time_delta_seconds"])
        self.assertIsNone(comparison["edge_halting_delta_seconds"])
        self.assertIsNone(comparison["final_arrival_delta_seconds"])

    def test_two_censored_visits_do_not_subtract_lower_bounds(self):
        n, d, nl, dl = fixture()
        censor(n, nl)
        censor(d, dl)
        d["per_vehicle"]["a"]["edge_visits"][0]["observed_followup_seconds"] = 1300
        result = paired_local_response(n, d, nl, dl)
        self.assertEqual(result["status"], "NOT_IDENTIFIABLE")
        self.assertEqual(result["vehicles_with_local_physical_response"], [])

    def test_no_edge_witness_and_missing_arrival_is_unknown(self):
        n, d, nl, dl = fixture()
        dl["a"].update(terminal_category="active", valid_non_teleported_arrival_seconds=None)
        self.assertEqual(paired_local_response(n, d, nl, dl)["status"], "NOT_IDENTIFIABLE")

    def test_completed_edge_witness_survives_unavailable_arrival(self):
        n, d, nl, dl = fixture()
        dl["a"].update(terminal_category="active", valid_non_teleported_arrival_seconds=None)
        d["per_vehicle"]["a"]["edge_visits"][0]["observed_edge_time_seconds"] = 11
        for field in ("exit_observed_at_seconds", "exit_transition_interval_start_seconds", "exit_transition_interval_end_seconds"):
            d["per_vehicle"]["a"]["edge_visits"][0][field] += 1
        self.assertEqual(paired_local_response(n, d, nl, dl)["status"], "PASS")

    def test_separate_fully_observed_witness_survives_unknown_vehicle(self):
        n, d, nl, dl = fixture()
        for s in (n, d):
            s["per_vehicle"]["b"] = copy.deepcopy(s["per_vehicle"]["a"])
            s["per_vehicle"]["b"]["edge_visits"][0]["vehicle_id"] = "b"
        nl["b"], dl["b"] = copy.deepcopy(nl["a"]), copy.deepcopy(dl["a"])
        d["unique_edge_entries"]["during"].append("b")
        d["unique_edge_entry_counts"]["during"] = 2
        censor(d, dl, "a")
        dl["b"]["valid_non_teleported_arrival_seconds"] = 401
        result = paired_local_response(n, d, nl, dl)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["vehicles_with_local_physical_response"], ["b"])
        self.assertTrue(result["unidentifiable_comparisons"])

    def test_arrival_witness_cannot_bypass_multiple_visit_ambiguity(self):
        n, d, nl, dl = fixture()
        n["per_vehicle"]["a"]["edge_visits"].append(copy.deepcopy(n["per_vehicle"]["a"]["edge_visits"][0]))
        dl["a"]["valid_non_teleported_arrival_seconds"] = 401
        self.assertEqual(paired_local_response(n, d, nl, dl)["status"], "NOT_IDENTIFIABLE")

    def test_pair_input_route_or_departure_mismatch_is_not_a_witness(self):
        for key, value in (("route_id", "row1_west"), ("scheduled_departure_seconds", 199)):
            with self.subTest(key=key):
                n, d, nl, dl = fixture()
                dl["a"][key] = value
                dl["a"]["valid_non_teleported_arrival_seconds"] = 401
                self.assertEqual(paired_local_response(n, d, nl, dl)["status"], "NOT_IDENTIFIABLE")

    def test_malformed_or_unfinalized_summary_is_not_observable_zero(self):
        n, d, nl, dl = fixture()
        for malformed in ({}, {"unique_edge_entries": {"during": []}}, {**d, "cutoff_seconds": 1499}):
            self.assertEqual(paired_local_response(n, malformed, nl, dl)["status"], "NOT_IDENTIFIABLE")

    def test_exact_complete_zero_exposure_is_identifiable_nonresponse(self):
        n, d, nl, dl = fixture()
        d["unique_edge_entries"]["during"] = []
        d["unique_edge_entry_counts"]["during"] = 0
        d["per_vehicle"] = {}
        self.assertEqual(paired_local_response(n, d, nl, dl)["status"], "FAIL")

    def test_duplicate_exposed_ids_are_unknown_not_double_counted(self):
        n, d, nl, dl = fixture()
        d["unique_edge_entries"]["during"] = ["a", "a"]
        self.assertEqual(paired_local_response(n, d, nl, dl)["status"], "NOT_IDENTIFIABLE")

    def test_unknown_status_and_missing_or_invalid_duration_cannot_witness(self):
        for key, value in (("visit_status", "UNKNOWN"), ("observed_edge_time_seconds", None), ("observed_edge_time_seconds", float("nan"))):
            with self.subTest(key=key, value=value):
                n, d, nl, dl = fixture()
                d["per_vehicle"]["a"]["edge_visits"][0][key] = value
                self.assertEqual(paired_local_response(n, d, nl, dl)["status"], "NOT_IDENTIFIABLE")

    def test_pairing_is_deterministic_and_does_not_mutate_inputs(self):
        args = fixture()
        before = copy.deepcopy(args)
        self.assertEqual(paired_local_response(*args), paired_local_response(*args))
        self.assertEqual(args, before)

    def test_explicitly_incomplete_zero_exposure_remains_unknown(self):
        n, d, nl, dl = fixture()
        d.update(exposure_observability_complete=False)
        d["unique_edge_entries"]["during"] = []
        d["unique_edge_entry_counts"]["during"] = 0
        d["per_vehicle"] = {}
        self.assertEqual(paired_local_response(n, d, nl, dl)["status"], "NOT_IDENTIFIABLE")

    def test_positive_edge_delta_does_not_survive_contradictory_arrival(self):
        n, d, nl, dl = fixture()
        v = d["per_vehicle"]["a"]["edge_visits"][0]
        v["observed_edge_time_seconds"] = 11
        for field in ("exit_observed_at_seconds", "exit_transition_interval_start_seconds", "exit_transition_interval_end_seconds"):
            v[field] += 1
        dl["a"]["valid_non_teleported_arrival_seconds"] = 100
        result = paired_local_response(n, d, nl, dl)
        self.assertEqual(result["status"], "NOT_IDENTIFIABLE")
        self.assertEqual(result["vehicles_with_local_physical_response"], [])

    def test_malformed_visit_identity_duration_or_interval_is_not_a_witness(self):
        for key, value in (("vehicle_id", "other"), ("occurrence_index", 2), ("entry_transition_interval_end_seconds", 309), ("observed_edge_time_seconds", 11)):
            n, d, nl, dl = fixture()
            d["per_vehicle"]["a"]["edge_visits"][0][key] = value
            self.assertEqual(paired_local_response(n, d, nl, dl)["status"], "NOT_IDENTIFIABLE")

    def test_actual_observer_outputs_feed_accounting_and_pairing(self):
        from scripts.b0.od_concentration_v2.cutoff_measurement import make_cutoff_observer, account_trips
        from test_b0_od_cutoff_v2 import FakeConnection, state, PUBLIC_OBSERVER

        def measured(last_step, arrival):
            observer = make_cutoff_observer(
                observer_path=PUBLIC_OBSERVER, run_id="SYNTHETIC",
                monitored_edges={"A1B1": ("A1B1_0", "A1B1_1")},
                passenger_class="passenger", event_start_seconds=300,
                event_end_seconds=600, pre_activation_time_seconds=300)
            conn = FakeConnection({t: {"a": state("A1B1", "A1B1_1")} for t in range(310, last_step + 1)})
            proxy = observer.wrap_connection(conn)
            for _ in range(1500):
                proxy.simulationStep()
            observer.finalize(1500)
            summary = observer.summary_payload(["a"])
            self.assertEqual(summary["per_vehicle"]["a"]["edge_visits"][0]["occurrence_index"], 0)
            accounting = account_trips(
                [{"vehicle_id": "a", "route_id": "row1_east", "scheduled_departure_seconds": 200}],
                tripinfo_records=[{"id": "a", "depart": 201, "arrival": -1 if arrival is None else arrival, "waitingTime": 0}],
                departed_events={"a": [201]}, arrival_events={} if arrival is None else {"a": [arrival]},
                cutoff_active_ids=["a"] if arrival is None else [], cutoff_pending_ids=[],
                per_trip_halting_seconds={"a": 0}, queue_trace=[[t, 0] for t in range(1, 1501)])
            self.assertEqual(accounting["measurement_status"], "VALID")
            return summary, accounting["ledger"]

        n, nl = measured(320, 400)
        d, dl = measured(321, 401)
        self.assertEqual(paired_local_response(n, d, nl, dl)["status"], "PASS")
        d, dl = measured(1500, None)
        self.assertEqual(paired_local_response(n, d, nl, dl)["status"], "NOT_IDENTIFIABLE")


if __name__ == "__main__":
    unittest.main()
