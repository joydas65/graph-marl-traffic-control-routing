"""Pure fake-trajectory tests; no simulator or operational runner is loaded."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.b0.od_concentration_v2 import cutoff_measurement as adapter


PUBLIC_OBSERVER = Path(__file__).resolve().parents[1] / "scripts/b0/exposure_observer.py"


def state(edge="X", lane="X_1", speed=5.0, position=10.0, route_index=1):
    return {"edge": edge, "lane": lane, "speed": speed,
            "position": position, "route_index": route_index}


class FakeConnection:
    def __init__(self, timeline):
        self.timeline = timeline
        self.time = 0.0
        self.states = {}
        self.restricted = False
        self.simulation = self
        self.vehicle = self
        self.lane = self

    def getTime(self):
        return self.time

    def simulationStep(self):
        self.time += 1
        self.states = copy.deepcopy(self.timeline.get(int(self.time), {}))

    def getIDList(self):
        return tuple(sorted(self.states))

    def getVehicleClass(self, vehicle_id):
        return "passenger"

    def getRoadID(self, vehicle_id):
        return self.states[vehicle_id]["edge"]

    def getLaneID(self, vehicle_id):
        return self.states[vehicle_id]["lane"]

    def getSpeed(self, vehicle_id):
        return self.states[vehicle_id]["speed"]

    def getLanePosition(self, vehicle_id):
        return self.states[vehicle_id]["position"]

    def getRouteIndex(self, vehicle_id):
        return self.states[vehicle_id]["route_index"]

    def getAllowed(self, lane_id):
        return []

    def getDisallowed(self, lane_id):
        return ["passenger"] if lane_id == "X_0" and self.restricted else []

    def __getattr__(self, name):
        if name.startswith(("set", "change", "reroute")):
            raise AssertionError(f"observer attempted a simulator setter: {name}")
        raise AttributeError(name)


def kwargs(end=4):
    return dict(run_id="OFFLINE", monitored_edges={"X": ("X_0", "X_1")},
                passenger_class="passenger", event_start_seconds=2,
                event_end_seconds=end, pre_activation_time_seconds=2)


def make(horizon=6, end=4):
    return adapter.make_cutoff_observer(observer_path=PUBLIC_OBSERVER,
                                       horizon_seconds=horizon, **kwargs(end))


def run(observer, timeline, horizon=6, end=4, disrupted=True):
    connection = FakeConnection(timeline)
    if hasattr(observer, "wrap_connection"):
        proxy = observer.wrap_connection(connection)
    else:
        historical = adapter.load_reviewed_observer(PUBLIC_OBSERVER)
        proxy = historical.ObservedConnection(connection, observer)
    for start in range(horizon):
        connection.restricted = disrupted and 2 <= start < end
        proxy.simulationStep()
    return connection


def normalize_new_summary(summary):
    result = copy.deepcopy(summary)
    for field in ("cutoff_seconds", "cutoff_monitored_states", "all_monitored_visits_completed"):
        result.pop(field)
    result["observer_identity"] = "B0_EXPOSURE_DIAGNOSTIC_V1"
    for per_vehicle in result["per_vehicle"].values():
        for visit in per_vehicle["edge_visits"] + per_vehicle["lane_visits"]:
            visit.pop("visit_status")
    for lane in result["lane_visit_diagnostics"].values():
        for visit in lane["visits"]:
            visit.pop("visit_status", None)
    return result


class CutoffObserverTests(unittest.TestCase):
    def test_complete_trajectory_matches_historical_scientific_fields(self):
        historical = adapter.load_reviewed_observer(PUBLIC_OBSERVER)
        timelines = [
            {},
            {1: {"v": state(lane="X_0")}, 2: {"v": state(speed=0)},
             3: {"v": state(speed=0, position=20)},
             4: {"v": state("Y", "Y_0", route_index=2)}},
        ]
        for timeline in timelines:
            with self.subTest(timeline=timeline):
                old, new = historical.ExposureObserver(**kwargs()), make()
                run(old, timeline)
                run(new, timeline)
                old.finalize(6)
                new.finalize(6)
                self.assertEqual(old.summary_payload({"v"}),
                                 normalize_new_summary(new.summary_payload({"v"})))
                for method in ("events_payload", "pre_activation_payload"):
                    old_payload = getattr(old, method)()
                    new_payload = getattr(new, method)()
                    self.assertEqual(new_payload.pop("observer_identity"), adapter.OBSERVER_IDENTITY)
                    old_payload.pop("observer_identity")
                    self.assertEqual(old_payload, new_payload)

    def test_active_edge_and_open_halting_are_censored_without_exit(self):
        timeline = {step: {"v": state(speed=0)} for step in range(3, 7)}
        observed = make()
        run(observed, timeline)
        events_before = copy.deepcopy(observed.events)
        observed.finalize(6)
        summary = observed.summary_payload({"v"})
        visit = summary["per_vehicle"]["v"]["edge_visits"][0]
        self.assertEqual(visit["visit_status"], adapter.RIGHT_CENSORED_AT_CUTOFF)
        self.assertIsNone(visit["exit_observed_at_seconds"])
        self.assertIsNone(visit["observed_edge_time_seconds"])
        self.assertEqual(visit["observed_followup_seconds"], 3)
        self.assertEqual(visit["observed_duration_lower_bound_seconds"], 3)
        self.assertEqual(visit["observed_halting_seconds"], 4)
        self.assertEqual(visit["last_state_observed_at_seconds"], 6)
        self.assertEqual(visit["entry_transition_interval_start_seconds"], 2)
        self.assertEqual(visit["entry_transition_interval_end_seconds"], 3)
        self.assertEqual(observed.events, events_before)
        self.assertFalse(any(event["event"].startswith("EXIT") for event in observed.events))
        self.assertTrue(summary["exposure_observability_complete"])
        self.assertFalse(summary["all_monitored_visits_completed"])
        self.assertEqual(summary["unique_edge_entry_counts"]["during"], 1)
        self.assertEqual(observed.open_edge_visits, {})

    def test_completed_lane_then_open_lane_preserves_occurrence(self):
        timeline = {1: {"v": state(lane="X_0")}}
        timeline.update({step: {"v": state()} for step in range(2, 7)})
        observed = make()
        run(observed, timeline)
        observed.finalize(6)
        visits = observed.summary_payload({"v"})["per_vehicle"]["v"]["lane_visits"]
        self.assertEqual([v["visit_status"] for v in visits],
                         [adapter.COMPLETED, adapter.RIGHT_CENSORED_AT_CUTOFF])
        self.assertEqual([v["edge_visit_occurrence"] for v in visits], [0, 0])
        self.assertEqual(visits[0]["observed_lane_time_seconds"], 1)
        self.assertIsNone(visits[1]["observed_lane_time_seconds"])
        self.assertEqual(visits[1]["lane_id"], "X_1")

    def test_exit_at_cutoff_is_completed_but_occupancy_is_censored(self):
        for exiting in (False, True):
            with self.subTest(exiting=exiting):
                timeline = {step: {"v": state()} for step in range(3, 7)}
                if exiting:
                    timeline[6] = {"v": state("Y", "Y_0", route_index=2)}
                observed = make()
                run(observed, timeline)
                observed.finalize(6)
                visit = observed.summary_payload({"v"})["per_vehicle"]["v"]["edge_visits"][0]
                self.assertEqual(visit["visit_status"], adapter.COMPLETED if exiting
                                 else adapter.RIGHT_CENSORED_AT_CUTOFF)
                self.assertEqual(visit["exit_observed_at_seconds"], 6 if exiting else None)

    def test_preexisting_occupancy_is_retained_without_new_entry(self):
        observed = make()
        run(observed, {step: {"v": state(lane="X_0")} for step in range(1, 7)})
        observed.finalize(6)
        summary = observed.summary_payload({"v"})
        lane = summary["lane_visit_diagnostics"]["X_0"]
        self.assertEqual(lane["preexisting_occupant_ids"], ["v"])
        self.assertEqual(lane["post_activation_entry_count"], 0)
        self.assertEqual(lane["visits"][0]["visit_classification"], "PREEXISTING_OCCUPANCY")
        self.assertEqual(summary["unique_edge_entry_counts"]["during"], 0)
        self.assertEqual([e["event"] for e in observed.events if e["event"] in
                          {"RESTRICTION_ACTIVATION", "RESTORATION"}],
                         ["RESTRICTION_ACTIVATION", "RESTORATION"])

    def test_reentry_still_open_at_cutoff_is_counted(self):
        timeline = {1: {"v": state(lane="X_0")}, 2: {"v": state(lane="X_0")},
                    3: {"v": state()}}
        timeline.update({step: {"v": state(lane="X_0")} for step in range(4, 8)})
        observed = make(horizon=7, end=5)
        run(observed, timeline, horizon=7, end=5)
        observed.finalize(7)
        lane = observed.summary_payload({"v"})["lane_visit_diagnostics"]["X_0"]
        self.assertEqual(lane["preexisting_occupant_ids"], ["v"])
        self.assertEqual(lane["post_activation_entry_ids"], ["v"])
        self.assertEqual(lane["post_activation_entry_count"], 1)
        self.assertEqual(lane["visits"][-1]["visit_classification"], "POST_ACTIVATION_ENTRY")

    def test_zero_exposure_is_complete_measurement(self):
        observed = make()
        run(observed, {})
        observed.finalize(6)
        summary = observed.summary_payload({"scheduled_but_not_observed"})
        self.assertTrue(summary["exposure_observability_complete"])
        self.assertEqual(summary["unique_edge_entry_counts"]["during"], 0)
        self.assertEqual(summary["lane_visit_diagnostics"]["X_0"]["post_activation_entry_count"], 0)
        self.assertEqual(summary["per_vehicle"]["scheduled_but_not_observed"]["edge_visits"], [])

    def test_full_1500_step_horizon_retains_event_entry_at_cutoff(self):
        observed = adapter.make_cutoff_observer(
            observer_path=PUBLIC_OBSERVER, run_id="FULL_H_OFFLINE",
            monitored_edges={"X": ("X_0", "X_1")}, passenger_class="passenger",
            event_start_seconds=300, event_end_seconds=600,
            pre_activation_time_seconds=300,
        )
        connection = FakeConnection({step: {"v": state(speed=0)}
                                     for step in range(301, 1501)})
        proxy = observed.wrap_connection(connection)
        for start in range(1500):
            connection.restricted = 300 <= start < 600
            proxy.simulationStep()
        observed.finalize(1500)
        summary = observed.summary_payload({"v"})
        visit = summary["per_vehicle"]["v"]["edge_visits"][0]
        self.assertEqual(summary["unique_edge_entry_counts"]["during"], 1)
        self.assertEqual(visit["cutoff_seconds"], 1500)
        self.assertEqual(visit["observed_followup_seconds"], 1199)
        self.assertEqual(visit["observed_halting_seconds"], 1200)
        self.assertEqual(visit["visit_status"], adapter.RIGHT_CENSORED_AT_CUTOFF)

    def test_open_visit_entry_periods_preserve_both_event_boundaries(self):
        for entry, period in ((2, "BEFORE"), (3, "DURING"), (4, "DURING"), (5, "AFTER")):
            with self.subTest(entry=entry):
                observed = make()
                run(observed, {step: {"v": state()} for step in range(entry, 7)})
                observed.finalize(6)
                summary = observed.summary_payload({"v"})
                visit = summary["per_vehicle"]["v"]["edge_visits"][0]
                self.assertEqual(visit["entry_period"], period)
                self.assertEqual(summary["unique_edge_entry_counts"]["during"],
                                 int(period == "DURING"))

    def test_active_off_monitored_edge_has_no_censored_visit(self):
        observed = make()
        run(observed, {step: {"v": state("Y", "Y_0")} for step in range(1, 7)})
        observed.finalize(6)
        self.assertTrue(observed.summary_payload({"v"})["all_monitored_visits_completed"])

    def test_missing_step_and_truncated_trace_fail_closed(self):
        observed = make()
        with self.assertRaises(adapter.ObservationError):
            observed.before_step(FakeConnection({}), 1)
        with self.assertRaises(adapter.ObservationError):
            observed.finalize(6)
        observed = make()
        run(observed, {}, horizon=5)
        with self.assertRaises(adapter.ObservationError):
            observed.finalize(6)
        with self.assertRaises(adapter.ObservationError):
            observed.summary_payload(set())

    def test_nonunit_and_duplicate_steps_are_invalid(self):
        observed = make()
        connection = FakeConnection({})
        observed.before_step(connection, 0)
        with self.assertRaises(adapter.ObservationError):
            observed.after_step(connection, 0, 2)
        observed = make()
        observed.before_step(connection, 0)
        with self.assertRaises(adapter.ObservationError):
            observed.before_step(connection, 0)

    def test_malformed_state_is_not_censoring(self):
        for malformed in (state(speed=float("nan")), state(speed=-1),
                          state(position=-1), state(lane="WRONG"),
                          state(route_index=-1)):
            with self.subTest(malformed=malformed):
                observed = make()
                with self.assertRaises((adapter.ObservationError, AssertionError)):
                    run(observed, {1: {"v": malformed}})
                with self.assertRaises(adapter.ObservationError):
                    observed.finalize(6)

    def test_decreasing_route_index_fails(self):
        observed = make()
        with self.assertRaises(adapter.ObservationError):
            run(observed, {1: {"v": state(route_index=2)},
                           2: {"v": state(route_index=1)}})

    def test_duplicate_vehicle_ids_fail(self):
        observed = make()
        connection = FakeConnection({1: {"v": state()}})
        connection.getIDList = lambda: ("v", "v")
        with self.assertRaises(adapter.ObservationError):
            observed.wrap_connection(connection).simulationStep()

    def test_event_order_and_open_identity_corruption_fail(self):
        for corrupt in ("event", "identity", "entry"):
            with self.subTest(corrupt=corrupt):
                observed = make()
                run(observed, {step: {"v": state()} for step in range(3, 7)})
                if corrupt == "event":
                    observed.events[-1]["sequence"] = 999
                elif corrupt == "identity":
                    observed.open_lane_visits["v"]["vehicle_id"] = "wrong"
                else:
                    observed.open_edge_visits["v"]["entry_observed_at_seconds"] = 100
                with self.assertRaises(adapter.ObservationError):
                    observed.finalize(6)

    def test_repeated_finalize_does_not_duplicate_or_mutate(self):
        observed = make()
        run(observed, {step: {"v": state()} for step in range(3, 7)})
        observed.finalize(6)
        before = json.dumps(observed.summary_payload({"v"}), sort_keys=True)
        with self.assertRaises(adapter.ObservationError):
            observed.finalize(6)
        self.assertEqual(before, json.dumps(observed.summary_payload({"v"}), sort_keys=True))

    def test_payload_repeatability(self):
        payloads = []
        for _ in range(2):
            observed = make()
            run(observed, {step: {"v": state()} for step in range(3, 7)})
            observed.finalize(6)
            payloads.append(json.dumps(observed.summary_payload({"v"}), sort_keys=True))
        self.assertEqual(*payloads)

    def test_dependency_path_and_hash_are_exact(self):
        with self.assertRaises(adapter.ObservationError):
            adapter.load_reviewed_observer(PUBLIC_OBSERVER.with_name("wrong.py"))
        with patch.object(Path, "read_bytes", return_value=b"changed bytes"):
            with self.assertRaises(adapter.ObservationError):
                adapter.load_reviewed_observer(PUBLIC_OBSERVER)


if __name__ == "__main__":
    unittest.main()
