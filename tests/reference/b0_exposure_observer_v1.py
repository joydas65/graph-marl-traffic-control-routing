from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "b0_exposure_observer_under_test", ROOT / "exposure_observer.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load exposure observer")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
ExposureObserver = MODULE.ExposureObserver
ObservedConnection = MODULE.ObservedConnection

import run_b0_exposure_diagnostic as RUNNER


def state(
    edge: str,
    lane: str,
    *,
    speed: float = 5.0,
    position: float = 10.0,
    route_index: int = 1,
    vehicle_class: str = "passenger",
) -> dict[str, object]:
    return {
        "edge": edge,
        "lane": lane,
        "speed": speed,
        "position": position,
        "route_index": route_index,
        "vehicle_class": vehicle_class,
    }


class FakeSimulation:
    def __init__(self) -> None:
        self.time = 0.0

    def getTime(self) -> float:
        return self.time


class FakeLane:
    def __init__(self, lanes: tuple[str, ...]) -> None:
        self.permissions = {
            lane: {"allowed": [], "disallowed": []} for lane in lanes
        }
        self.setter_accesses: list[str] = []

    def getAllowed(self, lane_id: str) -> list[str]:
        return list(self.permissions[lane_id]["allowed"])

    def getDisallowed(self, lane_id: str) -> list[str]:
        return list(self.permissions[lane_id]["disallowed"])

    def __getattr__(self, name: str):
        if name.startswith("set"):
            self.setter_accesses.append(name)
            raise AssertionError(f"observer attempted lane mutation {name}")
        raise AttributeError(name)


class FakeVehicle:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection
        self.setter_accesses: list[str] = []
        self.route_index_supported = True

    def getIDList(self) -> tuple[str, ...]:
        return tuple(sorted(self.connection.current_states))

    def getVehicleClass(self, vehicle_id: str) -> str:
        return str(self.connection.current_states[vehicle_id]["vehicle_class"])

    def getRoadID(self, vehicle_id: str) -> str:
        return str(self.connection.current_states[vehicle_id]["edge"])

    def getLaneID(self, vehicle_id: str) -> str:
        return str(self.connection.current_states[vehicle_id]["lane"])

    def getSpeed(self, vehicle_id: str) -> float:
        return float(self.connection.current_states[vehicle_id]["speed"])

    def getLanePosition(self, vehicle_id: str) -> float:
        return float(self.connection.current_states[vehicle_id]["position"])

    def getRouteIndex(self, vehicle_id: str) -> int:
        if not self.route_index_supported:
            raise NotImplementedError
        return int(self.connection.current_states[vehicle_id]["route_index"])

    def __getattr__(self, name: str):
        if name.startswith("set") or name.startswith("change") or name.startswith("reroute"):
            self.setter_accesses.append(name)
            raise AssertionError(f"observer attempted vehicle mutation {name}")
        raise AttributeError(name)


class FakeConnection:
    def __init__(
        self,
        timeline: dict[int, dict[str, dict[str, object]]],
        lanes: tuple[str, ...] = ("X_0", "X_1"),
    ) -> None:
        self.timeline = timeline
        self.simulation = FakeSimulation()
        self.current_states: dict[str, dict[str, object]] = copy.deepcopy(
            timeline.get(0, {})
        )
        self.lane = FakeLane(lanes)
        self.vehicle = FakeVehicle(self)

    def simulationStep(self) -> None:
        next_time = int(self.simulation.time + 1)
        self.current_states = copy.deepcopy(self.timeline.get(next_time, {}))
        self.simulation.time = float(next_time)


def observer(run_id: str = "TEST") -> object:
    return ExposureObserver(
        run_id=run_id,
        monitored_edges={"X": ("X_0", "X_1")},
        passenger_class="passenger",
        event_start_seconds=2,
        event_end_seconds=4,
        pre_activation_time_seconds=2,
    )


class ExposureObserverTests(unittest.TestCase):
    def test_entry_lane_change_and_exit_event_order(self) -> None:
        timeline = {
            1: {"v": state("X", "X_0")},
            2: {"v": state("X", "X_1", position=20)},
            3: {"v": state("Y", "Y_0", position=2)},
            4: {},
        }
        connection = FakeConnection(timeline)
        observed = observer()
        proxy = ObservedConnection(connection, observed)
        for _ in range(4):
            proxy.simulationStep()
        observed.finalize(4)
        vehicle_events = [
            item["event"] for item in observed.events if item["vehicle_id"] == "v"
        ]
        self.assertEqual(
            vehicle_events,
            [
                "ENTER_EDGE",
                "ENTER_LANE",
                "EXIT_LANE",
                "LANE_CHANGE",
                "ENTER_LANE",
                "EXIT_LANE",
                "EXIT_EDGE",
            ],
        )
        summary = observed.summary_payload({"v"})
        self.assertEqual(summary["per_vehicle"]["v"]["entry_periods"], ["BEFORE"])
        self.assertEqual(summary["lane_change_event_count"], 1)

    def test_pre_activation_snapshot_and_permission_boundaries(self) -> None:
        timeline = {
            1: {},
            2: {"v": state("X", "X_1", position=25)},
            3: {"v": state("X", "X_1", position=35)},
            4: {"v": state("X", "X_1", position=45)},
            5: {"v": state("Y", "Y_0")},
        }
        connection = FakeConnection(timeline)
        observed = observer()
        proxy = ObservedConnection(connection, observed)
        proxy.simulationStep()
        proxy.simulationStep()
        connection.lane.permissions["X_0"]["disallowed"] = ["passenger"]
        proxy.simulationStep()
        proxy.simulationStep()
        connection.lane.permissions["X_0"]["disallowed"] = []
        proxy.simulationStep()
        observed.finalize(5)

        snapshot = observed.pre_activation_payload()
        self.assertEqual(snapshot["simulation_time_seconds"], 2.0)
        self.assertEqual(snapshot["lane_occupancy"], {"X_0": 0, "X_1": 1})
        permission_events = [
            (item["event"], item["observed_at_seconds"])
            for item in observed.events
            if item["event"] in {"RESTRICTION_ACTIVATION", "RESTORATION"}
        ]
        self.assertEqual(
            permission_events,
            [("RESTRICTION_ACTIVATION", 2.0), ("RESTORATION", 4.0)],
        )
        summary = observed.summary_payload({"v"})
        self.assertEqual(summary["unique_event_lane_users"]["X_1"], ["v"])
        self.assertEqual(summary["unique_edge_entry_counts"]["before"], 1)

    def test_preactivation_lane_user_exiting_first_event_step_is_retained(self) -> None:
        timeline = {
            1: {},
            2: {"v": state("X", "X_0", position=170)},
            3: {"v": state("Y", "Y_0", position=3)},
            4: {},
        }
        connection = FakeConnection(timeline)
        observed = observer()
        proxy = ObservedConnection(connection, observed)
        proxy.simulationStep()
        proxy.simulationStep()
        connection.lane.permissions["X_0"]["disallowed"] = ["passenger"]
        proxy.simulationStep()
        proxy.simulationStep()
        observed.finalize(4)

        summary = observed.summary_payload({"v"})
        self.assertEqual(summary["unique_event_lane_users"]["X_0"], ["v"])
        self.assertEqual(summary["preexisting_event_lane_users"]["X_0"], ["v"])
        self.assertEqual(summary["new_event_lane_users"]["X_0"], [])

    def test_preexisting_restricted_lane_occupancy_is_not_a_violation(self) -> None:
        timeline = {
            1: {"v": state("X", "X_0", position=140)},
            2: {"v": state("X", "X_0", position=150)},
            3: {"v": state("X", "X_0", position=160)},
            4: {"v": state("Y", "Y_0", position=3)},
            5: {},
        }
        connection = FakeConnection(timeline)
        observed = observer()
        proxy = ObservedConnection(connection, observed)
        proxy.simulationStep()
        proxy.simulationStep()
        connection.lane.permissions["X_0"]["disallowed"] = ["passenger"]
        proxy.simulationStep()
        proxy.simulationStep()
        connection.lane.permissions["X_0"]["disallowed"] = []
        proxy.simulationStep()
        observed.finalize(5)

        summary = observed.summary_payload({"v"})
        lane = summary["lane_visit_diagnostics"]["X_0"]
        compliance = RUNNER.restricted_lane_compliance(
            summary,
            observed.events,
            restricted_lane="X_0",
            activation_time=2,
            restoration_time=4,
        )
        self.assertEqual(lane["preexisting_occupant_ids"], ["v"])
        self.assertEqual(lane["post_activation_entry_count"], 0)
        self.assertEqual(compliance["status"], "PASS")

    def test_preexisting_vehicle_reentry_is_a_compliance_violation(self) -> None:
        timeline = {
            1: {"v": state("X", "X_0", position=120)},
            2: {"v": state("X", "X_0", position=130)},
            3: {"v": state("X", "X_1", position=140)},
            4: {"v": state("X", "X_0", position=150)},
            5: {"v": state("Y", "Y_0", position=3)},
            6: {},
        }
        connection = FakeConnection(timeline)
        observed = observer()
        proxy = ObservedConnection(connection, observed)
        proxy.simulationStep()
        proxy.simulationStep()
        connection.lane.permissions["X_0"]["disallowed"] = ["passenger"]
        proxy.simulationStep()
        proxy.simulationStep()
        connection.lane.permissions["X_0"]["disallowed"] = []
        proxy.simulationStep()
        proxy.simulationStep()
        observed.finalize(6)

        summary = observed.summary_payload({"v"})
        lane = summary["lane_visit_diagnostics"]["X_0"]
        compliance = RUNNER.restricted_lane_compliance(
            summary,
            observed.events,
            restricted_lane="X_0",
            activation_time=2,
            restoration_time=4,
        )
        self.assertEqual(lane["preexisting_occupant_ids"], ["v"])
        self.assertEqual(lane["post_activation_entry_ids"], ["v"])
        self.assertEqual(lane["post_activation_entry_count"], 1)
        self.assertEqual(
            [
                visit["entry_period"]
                for visit in lane["visits"]
                if visit["vehicle_id"] == "v"
            ],
            ["BEFORE", "DURING"],
        )
        self.assertEqual(compliance["status"], "FAIL")

    def test_zero_edge_exposure_is_observable_not_an_integrity_failure(self) -> None:
        connection = FakeConnection({1: {}, 2: {}, 3: {}, 4: {}, 5: {}})
        observed = observer()
        proxy = ObservedConnection(connection, observed)
        proxy.simulationStep()
        proxy.simulationStep()
        connection.lane.permissions["X_0"]["disallowed"] = ["passenger"]
        proxy.simulationStep()
        proxy.simulationStep()
        connection.lane.permissions["X_0"]["disallowed"] = []
        proxy.simulationStep()
        observed.finalize(5)

        summary = observed.summary_payload(set())
        compliance = RUNNER.restricted_lane_compliance(
            summary,
            observed.events,
            restricted_lane="X_0",
            activation_time=2,
            restoration_time=4,
        )
        self.assertEqual(summary["unique_edge_entry_counts"]["during"], 0)
        self.assertTrue(summary["exposure_observability_complete"])
        self.assertEqual(compliance["status"], "PASS")
        self.assertEqual(
            RUNNER.determine_diagnostic_status(
                scientific_noninterference=True,
                determinism_pass=True,
                static_noninterference_pass=True,
                original_evidence_unchanged=True,
                lifecycle_observed=True,
                compliance_observed=True,
                exposure_observability_complete=True,
                paired_diagnostics_status="PASS",
            ),
            "PASS",
        )

    def test_event_period_visit_selection_and_ambiguity(self) -> None:
        def visit(
            occurrence: int,
            interval_start: float,
            interval_end: float,
            route_index: int,
        ) -> dict[str, object]:
            return {
                "edge_id": "X",
                "occurrence_index": occurrence,
                "entry_transition_interval_start_seconds": interval_start,
                "entry_transition_interval_end_seconds": interval_end,
                "entry_observed_at_seconds": interval_end,
                "entry_route_index": route_index,
            }

        n0_visits = [visit(0, 250, 251, 0), visit(1, 350, 351, 1)]
        d0_visits = [visit(0, 250, 251, 0), visit(1, 350, 351, 1)]
        selected = RUNNER.select_event_period_visit_pair(
            n0_visits,
            d0_visits,
            event_start=300,
            event_end=600,
            monitored_edge="X",
        )
        self.assertEqual(selected["status"], "IDENTIFIED")
        self.assertEqual(selected["n0_visit"]["occurrence_index"], 1)
        self.assertEqual(selected["d0_visit"]["occurrence_index"], 1)
        self.assertEqual(selected["d0_visit"]["entry_observed_at_seconds"], 351)

        ambiguous = RUNNER.select_event_period_visit_pair(
            n0_visits,
            d0_visits + [visit(2, 450, 451, 1)],
            event_start=300,
            event_end=600,
            monitored_edge="X",
        )
        self.assertEqual(ambiguous["status"], "NOT_IDENTIFIABLE")
        self.assertEqual(
            ambiguous["reason"], "D0_EVENT_PERIOD_VISIT_NOT_UNIQUE"
        )

    def test_end_endpoint_transition_is_during_active_interval(self) -> None:
        timeline = {
            1: {},
            2: {},
            3: {},
            4: {"v": state("X", "X_1")},
            5: {"v": state("Y", "Y_0")},
        }
        connection = FakeConnection(timeline)
        observed = observer()
        proxy = ObservedConnection(connection, observed)
        for _ in range(5):
            proxy.simulationStep()
        observed.finalize(5)
        visit = observed.summary_payload({"v"})["per_vehicle"]["v"]["edge_visits"][0]
        self.assertEqual(visit["entry_transition_interval_start_seconds"], 3.0)
        self.assertEqual(visit["entry_transition_interval_end_seconds"], 4.0)
        self.assertEqual(observed.summary_payload({"v"})["unique_edge_entries"]["during"], ["v"])

    def test_entry_after_restoration_is_after_event(self) -> None:
        timeline = {
            1: {},
            2: {},
            3: {},
            4: {},
            5: {"v": state("X", "X_1")},
            6: {"v": state("Y", "Y_0")},
        }
        connection = FakeConnection(timeline)
        observed = observer()
        proxy = ObservedConnection(connection, observed)
        for _ in range(6):
            proxy.simulationStep()
        observed.finalize(6)
        self.assertEqual(observed.summary_payload({"v"})["unique_edge_entries"]["after"], ["v"])

    def test_non_passenger_is_excluded(self) -> None:
        timeline = {
            1: {"bus": state("X", "X_0", vehicle_class="bus")},
            2: {},
            3: {},
        }
        connection = FakeConnection(timeline)
        observed = observer()
        proxy = ObservedConnection(connection, observed)
        for _ in range(3):
            proxy.simulationStep()
        observed.finalize(3)
        self.assertEqual(observed.events, [])

    def test_wait_start_end_and_halting_integral(self) -> None:
        timeline = {
            1: {"v": state("X", "X_0", speed=0.0)},
            2: {"v": state("X", "X_0", speed=1.0)},
            3: {"v": state("Y", "Y_0")},
            4: {},
        }
        connection = FakeConnection(timeline)
        observed = observer()
        proxy = ObservedConnection(connection, observed)
        for _ in range(4):
            proxy.simulationStep()
        observed.finalize(4)
        events = [item["event"] for item in observed.events]
        self.assertIn("WAIT_START", events)
        self.assertIn("WAIT_END", events)
        self.assertEqual(
            observed.summary_payload({"v"})["per_vehicle"]["v"][
                "observed_edge_halting_seconds"
            ],
            1.0,
        )

    def test_route_index_unavailable_is_recorded_as_null(self) -> None:
        timeline = {
            1: {"v": state("X", "X_0")},
            2: {"v": state("Y", "Y_0")},
            3: {},
        }
        connection = FakeConnection(timeline)
        connection.vehicle.route_index_supported = False
        observed = observer()
        proxy = ObservedConnection(connection, observed)
        for _ in range(3):
            proxy.simulationStep()
        observed.finalize(3)
        entry = next(item for item in observed.events if item["event"] == "ENTER_EDGE")
        self.assertIsNone(entry["route_index"])

    def test_arbitrary_configured_edge_and_no_setter_access(self) -> None:
        timeline = {
            1: {},
            2: {"v": state("Q", "Q_7")},
            3: {"v": state("R", "R_0")},
            4: {},
        }
        connection = FakeConnection(timeline, lanes=("Q_7",))
        observed = ExposureObserver(
            run_id="ALT",
            monitored_edges={"Q": ("Q_7",)},
            passenger_class="passenger",
            event_start_seconds=1,
            event_end_seconds=2,
            pre_activation_time_seconds=1,
        )
        proxy = ObservedConnection(connection, observed)
        for _ in range(4):
            proxy.simulationStep()
        observed.finalize(4)
        self.assertEqual(connection.lane.setter_accesses, [])
        self.assertEqual(connection.vehicle.setter_accesses, [])
        self.assertEqual(observed.summary_payload({"v"})["unique_edge_entries"]["during"], ["v"])

    def test_transition_between_two_monitored_edges_closes_both_visits(self) -> None:
        timeline = {
            1: {"v": state("X", "X_0")},
            2: {"v": state("Q", "Q_0")},
            3: {"v": state("R", "R_0")},
            4: {},
        }
        connection = FakeConnection(timeline, lanes=("X_0", "Q_0"))
        observed = ExposureObserver(
            run_id="MULTI",
            monitored_edges={"X": ("X_0",), "Q": ("Q_0",)},
            passenger_class="passenger",
            event_start_seconds=2,
            event_end_seconds=4,
            pre_activation_time_seconds=2,
        )
        proxy = ObservedConnection(connection, observed)
        for _ in range(4):
            proxy.simulationStep()
        observed.finalize(4)

        summary = observed.summary_payload({"v"})
        visits = summary["per_vehicle"]["v"]["edge_visits"]
        self.assertEqual([visit["edge_id"] for visit in visits], ["X", "Q"])
        self.assertEqual(observed.open_edge_visits, {})
        self.assertEqual(observed.open_lane_visits, {})

    def test_normalized_payload_is_repeatable(self) -> None:
        timeline = {
            1: {"v": state("X", "X_0")},
            2: {"v": state("Y", "Y_0")},
            3: {},
        }
        payloads = []
        for run_id in ("FIRST", "REPEAT"):
            connection = FakeConnection(timeline)
            observed = observer(run_id)
            proxy = ObservedConnection(connection, observed)
            for _ in range(3):
                proxy.simulationStep()
            observed.finalize(3)
            payload = observed.events_payload()
            payload.pop("run_id")
            payloads.append(json.dumps(payload, sort_keys=True))
        self.assertEqual(payloads[0], payloads[1])


if __name__ == "__main__":
    unittest.main()
