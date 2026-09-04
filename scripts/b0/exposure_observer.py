"""Read-only, event-style per-vehicle edge/lane exposure observer.

The observer samples one-second TraCI state without issuing vehicle, route,
traffic-light, lane, or vehicle-type mutations.  Transition timestamps are
reported as observation intervals so a crossing is not represented as having
sub-second precision that the diagnostic does not possess.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


OBSERVER_IDENTITY = "B0_EXPOSURE_DIAGNOSTIC_V1"
HALTING_SPEED_MPS = 0.1


def _number(value: float) -> float:
    """Return a stable finite-resolution number for deterministic evidence."""

    return float(f"{float(value):.6f}")


def _passenger_allowed(permissions: Mapping[str, list[str]], vehicle_class: str) -> bool:
    allowed = permissions["allowed"]
    disallowed = permissions["disallowed"]
    return (not allowed or vehicle_class in allowed) and vehicle_class not in disallowed


@dataclass(frozen=True)
class VehicleState:
    vehicle_id: str
    edge_id: str
    lane_id: str
    speed_mps: float
    lane_position_metres: float
    route_index: int | None

    def payload(self) -> dict[str, Any]:
        return asdict(self)


class ExposureObserver:
    """Observe transitions for a configured edge and configured lane set."""

    def __init__(
        self,
        *,
        run_id: str,
        monitored_edges: Mapping[str, Iterable[str]],
        passenger_class: str,
        event_start_seconds: float,
        event_end_seconds: float,
        pre_activation_time_seconds: float,
    ) -> None:
        normalized = {
            str(edge_id): tuple(sorted({str(lane_id) for lane_id in lane_ids}))
            for edge_id, lane_ids in monitored_edges.items()
        }
        if not normalized or any(not lanes for lanes in normalized.values()):
            raise ValueError("at least one monitored edge with at least one lane is required")
        if event_end_seconds <= event_start_seconds:
            raise ValueError("event interval must be non-empty")

        self.run_id = run_id
        self.monitored_edges = dict(sorted(normalized.items()))
        self.monitored_lanes = tuple(
            sorted(lane_id for lanes in self.monitored_edges.values() for lane_id in lanes)
        )
        if len(self.monitored_lanes) != len(set(self.monitored_lanes)):
            raise ValueError("a monitored lane may belong to only one monitored edge")
        self.passenger_class = passenger_class
        self.event_start_seconds = float(event_start_seconds)
        self.event_end_seconds = float(event_end_seconds)
        self.pre_activation_time_seconds = float(pre_activation_time_seconds)

        self.events: list[dict[str, Any]] = []
        self.previous_on_edge: dict[str, VehicleState] = {}
        self.last_permissions: dict[str, dict[str, list[str]]] = {}
        self.pre_activation_states: list[VehicleState] | None = None
        self.edge_visits: dict[str, list[dict[str, Any]]] = {}
        self.lane_visits: dict[str, list[dict[str, Any]]] = {}
        self.open_edge_visits: dict[str, dict[str, Any]] = {}
        self.open_lane_visits: dict[str, dict[str, Any]] = {}
        self.edge_halting_seconds: dict[str, float] = {}
        self.event_lane_users: dict[str, set[str]] = {
            lane_id: set() for lane_id in self.monitored_lanes
        }
        self.preexisting_event_lane_users: dict[str, set[str]] = {
            lane_id: set() for lane_id in self.monitored_lanes
        }
        self.event_edge_users: dict[str, set[str]] = {
            edge_id: set() for edge_id in self.monitored_edges
        }
        self.last_interval_end: float | None = None
        self.finalized = False
        self._sequence = 0

    @staticmethod
    def _permissions(connection: Any, lane_id: str) -> dict[str, list[str]]:
        return {
            "allowed": sorted(connection.lane.getAllowed(lane_id)),
            "disallowed": sorted(connection.lane.getDisallowed(lane_id)),
        }

    @staticmethod
    def _state(connection: Any, vehicle_id: str, edge_id: str | None = None) -> VehicleState:
        observed_edge = connection.vehicle.getRoadID(vehicle_id) if edge_id is None else edge_id
        try:
            route_index: int | None = int(connection.vehicle.getRouteIndex(vehicle_id))
        except (AttributeError, NotImplementedError):
            route_index = None
        return VehicleState(
            vehicle_id=str(vehicle_id),
            edge_id=str(observed_edge),
            lane_id=str(connection.vehicle.getLaneID(vehicle_id)),
            speed_mps=_number(connection.vehicle.getSpeed(vehicle_id)),
            lane_position_metres=_number(connection.vehicle.getLanePosition(vehicle_id)),
            route_index=route_index,
        )

    def _append_event(
        self,
        event: str,
        *,
        observed_at_seconds: float,
        interval_start_seconds: float,
        interval_end_seconds: float,
        state: VehicleState | None = None,
        state_observed_at_seconds: float | None = None,
        **details: Any,
    ) -> None:
        self._sequence += 1
        payload: dict[str, Any] = {
            "sequence": self._sequence,
            "event": event,
            "observed_at_seconds": _number(observed_at_seconds),
            "transition_interval_start_seconds": _number(interval_start_seconds),
            "transition_interval_end_seconds": _number(interval_end_seconds),
            "vehicle_id": None,
            "edge_id": None,
            "lane_id": None,
            "speed_mps": None,
            "lane_position_metres": None,
            "route_index": None,
            "state_observed_at_seconds": None,
        }
        if state is not None:
            payload.update(state.payload())
            payload["state_observed_at_seconds"] = _number(
                observed_at_seconds
                if state_observed_at_seconds is None
                else state_observed_at_seconds
            )
        payload.update(details)
        self.events.append(payload)

    def _interval_overlaps_event(self, start: float, end: float) -> bool:
        return start < self.event_end_seconds and end > self.event_start_seconds

    def before_step(self, connection: Any, simulation_time_seconds: float) -> None:
        """Observe permission transitions after frozen events and before a step."""

        timestamp = float(simulation_time_seconds)
        for lane_id in self.monitored_lanes:
            current = self._permissions(connection, lane_id)
            previous = self.last_permissions.get(lane_id)
            if previous is None:
                self.last_permissions[lane_id] = current
                continue
            if current == previous:
                continue
            was_allowed = _passenger_allowed(previous, self.passenger_class)
            now_allowed = _passenger_allowed(current, self.passenger_class)
            if was_allowed and not now_allowed:
                event = "RESTRICTION_ACTIVATION"
            elif not was_allowed and now_allowed:
                event = "RESTORATION"
            else:
                event = "PERMISSION_CHANGE"
            edge_id = next(
                edge
                for edge, lane_ids in self.monitored_edges.items()
                if lane_id in lane_ids
            )
            self._append_event(
                event,
                observed_at_seconds=timestamp,
                interval_start_seconds=timestamp,
                interval_end_seconds=timestamp,
                edge_id=edge_id,
                lane_id=lane_id,
                before_permissions=previous,
                after_permissions=current,
            )
            if event == "RESTRICTION_ACTIVATION":
                if self.pre_activation_states is None:
                    raise AssertionError(
                        "restriction activation lacks the pre-activation snapshot"
                    )
                for state in self.pre_activation_states:
                    if state.lane_id == lane_id:
                        open_visit = self.open_lane_visits.get(state.vehicle_id)
                        if (
                            open_visit is not None
                            and open_visit["lane_id"] == lane_id
                        ):
                            open_visit[
                                "restriction_activation_observed_while_open"
                            ] = True
                        self.preexisting_event_lane_users[lane_id].add(
                            state.vehicle_id
                        )
                        self.event_lane_users[lane_id].add(state.vehicle_id)
                        self.event_edge_users[state.edge_id].add(state.vehicle_id)
            self.last_permissions[lane_id] = current

    def after_step(
        self,
        connection: Any,
        interval_start_seconds: float,
        interval_end_seconds: float,
    ) -> None:
        """Sample passenger state and emit only relevant transition events."""

        start = float(interval_start_seconds)
        end = float(interval_end_seconds)
        if end <= start:
            raise AssertionError("observer received a non-positive simulation interval")
        self.last_interval_end = end

        active_ids = sorted(str(item) for item in connection.vehicle.getIDList())
        active_states: dict[str, VehicleState] = {}
        current_on_edge: dict[str, VehicleState] = {}
        for vehicle_id in active_ids:
            if connection.vehicle.getVehicleClass(vehicle_id) != self.passenger_class:
                continue
            edge_id = str(connection.vehicle.getRoadID(vehicle_id))
            if edge_id in self.monitored_edges or vehicle_id in self.previous_on_edge:
                state = self._state(connection, vehicle_id, edge_id)
                active_states[vehicle_id] = state
                if edge_id in self.monitored_edges:
                    if state.lane_id not in self.monitored_edges[edge_id]:
                        raise AssertionError(
                            f"vehicle {vehicle_id} is on monitored edge {edge_id} "
                            f"but unconfigured lane {state.lane_id}"
                        )
                    current_on_edge[vehicle_id] = state

        if self._interval_overlaps_event(start, end):
            for previous in self.previous_on_edge.values():
                self.event_edge_users[previous.edge_id].add(previous.vehicle_id)
                self.event_lane_users[previous.lane_id].add(previous.vehicle_id)

        for vehicle_id in sorted(set(self.previous_on_edge) - set(current_on_edge)):
            previous = self.previous_on_edge[vehicle_id]
            following = active_states.get(vehicle_id)
            if previous.speed_mps < HALTING_SPEED_MPS:
                self._append_event(
                    "WAIT_END",
                    observed_at_seconds=end,
                    interval_start_seconds=start,
                    interval_end_seconds=end,
                    state=previous,
                    state_observed_at_seconds=start,
                )
            self._close_lane_visit(vehicle_id, previous, start, end)
            self._append_event(
                "EXIT_LANE",
                observed_at_seconds=end,
                interval_start_seconds=start,
                interval_end_seconds=end,
                state=previous,
                state_observed_at_seconds=start,
                next_edge_id=None if following is None else following.edge_id,
                next_lane_id=None if following is None else following.lane_id,
            )
            self._close_edge_visit(vehicle_id, previous, start, end)
            self._append_event(
                "EXIT_EDGE",
                observed_at_seconds=end,
                interval_start_seconds=start,
                interval_end_seconds=end,
                state=previous,
                state_observed_at_seconds=start,
                next_edge_id=None if following is None else following.edge_id,
                next_lane_id=None if following is None else following.lane_id,
            )

        for vehicle_id in sorted(current_on_edge):
            current = current_on_edge[vehicle_id]
            previous = self.previous_on_edge.get(vehicle_id)
            if previous is None:
                self._open_edge_visit(vehicle_id, current, start, end)
                self._append_event(
                    "ENTER_EDGE",
                    observed_at_seconds=end,
                    interval_start_seconds=start,
                    interval_end_seconds=end,
                    state=current,
                )
                self._open_lane_visit(vehicle_id, current, start, end)
                self._append_event(
                    "ENTER_LANE",
                    observed_at_seconds=end,
                    interval_start_seconds=start,
                    interval_end_seconds=end,
                    state=current,
                )
                if current.speed_mps < HALTING_SPEED_MPS:
                    self._append_event(
                        "WAIT_START",
                        observed_at_seconds=end,
                        interval_start_seconds=start,
                        interval_end_seconds=end,
                        state=current,
                    )
            elif current.edge_id != previous.edge_id:
                if previous.speed_mps < HALTING_SPEED_MPS:
                    self._append_event(
                        "WAIT_END",
                        observed_at_seconds=end,
                        interval_start_seconds=start,
                        interval_end_seconds=end,
                        state=previous,
                        state_observed_at_seconds=start,
                    )
                self._close_lane_visit(vehicle_id, previous, start, end)
                self._append_event(
                    "EXIT_LANE",
                    observed_at_seconds=end,
                    interval_start_seconds=start,
                    interval_end_seconds=end,
                    state=previous,
                    state_observed_at_seconds=start,
                    next_edge_id=current.edge_id,
                    next_lane_id=current.lane_id,
                )
                self._close_edge_visit(vehicle_id, previous, start, end)
                self._append_event(
                    "EXIT_EDGE",
                    observed_at_seconds=end,
                    interval_start_seconds=start,
                    interval_end_seconds=end,
                    state=previous,
                    state_observed_at_seconds=start,
                    next_edge_id=current.edge_id,
                    next_lane_id=current.lane_id,
                )
                self._open_edge_visit(vehicle_id, current, start, end)
                self._append_event(
                    "ENTER_EDGE",
                    observed_at_seconds=end,
                    interval_start_seconds=start,
                    interval_end_seconds=end,
                    state=current,
                    previous_edge_id=previous.edge_id,
                )
                self._open_lane_visit(vehicle_id, current, start, end)
                self._append_event(
                    "ENTER_LANE",
                    observed_at_seconds=end,
                    interval_start_seconds=start,
                    interval_end_seconds=end,
                    state=current,
                    previous_edge_id=previous.edge_id,
                    previous_lane_id=previous.lane_id,
                )
                if current.speed_mps < HALTING_SPEED_MPS:
                    self._append_event(
                        "WAIT_START",
                        observed_at_seconds=end,
                        interval_start_seconds=start,
                        interval_end_seconds=end,
                        state=current,
                    )
            elif current.lane_id != previous.lane_id:
                if previous.speed_mps < HALTING_SPEED_MPS:
                    self._append_event(
                        "WAIT_END",
                        observed_at_seconds=end,
                        interval_start_seconds=start,
                        interval_end_seconds=end,
                        state=previous,
                        state_observed_at_seconds=start,
                    )
                self._close_lane_visit(vehicle_id, previous, start, end)
                self._append_event(
                    "EXIT_LANE",
                    observed_at_seconds=end,
                    interval_start_seconds=start,
                    interval_end_seconds=end,
                    state=previous,
                    state_observed_at_seconds=start,
                    next_edge_id=current.edge_id,
                    next_lane_id=current.lane_id,
                )
                self._append_event(
                    "LANE_CHANGE",
                    observed_at_seconds=end,
                    interval_start_seconds=start,
                    interval_end_seconds=end,
                    state=current,
                    previous_lane_id=previous.lane_id,
                    new_lane_id=current.lane_id,
                )
                self._open_lane_visit(vehicle_id, current, start, end)
                self._append_event(
                    "ENTER_LANE",
                    observed_at_seconds=end,
                    interval_start_seconds=start,
                    interval_end_seconds=end,
                    state=current,
                    previous_lane_id=previous.lane_id,
                )
                if current.speed_mps < HALTING_SPEED_MPS:
                    self._append_event(
                        "WAIT_START",
                        observed_at_seconds=end,
                        interval_start_seconds=start,
                        interval_end_seconds=end,
                        state=current,
                    )
            elif previous.speed_mps >= HALTING_SPEED_MPS > current.speed_mps:
                self._append_event(
                    "WAIT_START",
                    observed_at_seconds=end,
                    interval_start_seconds=start,
                    interval_end_seconds=end,
                    state=current,
                )
            elif previous.speed_mps < HALTING_SPEED_MPS <= current.speed_mps:
                self._append_event(
                    "WAIT_END",
                    observed_at_seconds=end,
                    interval_start_seconds=start,
                    interval_end_seconds=end,
                    state=current,
                )

            if current.speed_mps < HALTING_SPEED_MPS:
                self.edge_halting_seconds[vehicle_id] = _number(
                    self.edge_halting_seconds.get(vehicle_id, 0.0) + (end - start)
                )
                open_visit = self.open_edge_visits[vehicle_id]
                open_visit["observed_halting_seconds"] = _number(
                    float(open_visit["observed_halting_seconds"]) + (end - start)
                )
            if self._interval_overlaps_event(start, end):
                self.event_edge_users[current.edge_id].add(vehicle_id)
                self.event_lane_users[current.lane_id].add(vehicle_id)

        if end == self.pre_activation_time_seconds:
            permissions = {
                lane_id: self._permissions(connection, lane_id)
                for lane_id in self.monitored_lanes
            }
            if not all(
                _passenger_allowed(value, self.passenger_class)
                for value in permissions.values()
            ):
                raise AssertionError("pre-activation snapshot was not taken before restriction")
            self.pre_activation_states = [
                current_on_edge[vehicle_id]
                for vehicle_id in sorted(current_on_edge)
            ]
            for state in self.pre_activation_states:
                self.preexisting_event_lane_users[state.lane_id].add(state.vehicle_id)

        self.previous_on_edge = current_on_edge

    def _open_edge_visit(
        self, vehicle_id: str, state: VehicleState, start: float, end: float
    ) -> None:
        if vehicle_id in self.open_edge_visits:
            raise AssertionError(f"duplicate open edge visit for {vehicle_id}")
        same_edge_visit_count = sum(
            visit["edge_id"] == state.edge_id
            for visit in self.edge_visits.get(vehicle_id, [])
        )
        self.open_edge_visits[vehicle_id] = {
            "vehicle_id": vehicle_id,
            "occurrence_index": same_edge_visit_count,
            "edge_id": state.edge_id,
            "entry_observed_at_seconds": _number(end),
            "entry_transition_interval_start_seconds": _number(start),
            "entry_transition_interval_end_seconds": _number(end),
            "entry_lane_id": state.lane_id,
            "entry_speed_mps": state.speed_mps,
            "entry_lane_position_metres": state.lane_position_metres,
            "entry_route_index": state.route_index,
            "observed_halting_seconds": 0.0,
        }

    def _close_edge_visit(
        self, vehicle_id: str, state: VehicleState, start: float, end: float
    ) -> None:
        visit = self.open_edge_visits.pop(vehicle_id)
        visit.update(
            {
                "exit_observed_at_seconds": _number(end),
                "exit_transition_interval_start_seconds": _number(start),
                "exit_transition_interval_end_seconds": _number(end),
                "last_lane_id": state.lane_id,
                "last_speed_mps": state.speed_mps,
                "last_lane_position_metres": state.lane_position_metres,
                "last_state_observed_at_seconds": _number(start),
                "observed_edge_time_seconds": _number(
                    end - float(visit["entry_observed_at_seconds"])
                ),
            }
        )
        self.edge_visits.setdefault(vehicle_id, []).append(visit)

    def _open_lane_visit(
        self, vehicle_id: str, state: VehicleState, start: float, end: float
    ) -> None:
        if vehicle_id in self.open_lane_visits:
            raise AssertionError(f"duplicate open lane visit for {vehicle_id}")
        if vehicle_id not in self.open_edge_visits:
            raise AssertionError(f"lane visit lacks an open edge visit for {vehicle_id}")
        self.open_lane_visits[vehicle_id] = {
            "vehicle_id": vehicle_id,
            "edge_visit_occurrence": self.open_edge_visits[vehicle_id][
                "occurrence_index"
            ],
            "edge_id": state.edge_id,
            "lane_id": state.lane_id,
            "entry_observed_at_seconds": _number(end),
            "entry_transition_interval_start_seconds": _number(start),
            "entry_transition_interval_end_seconds": _number(end),
            "entry_speed_mps": state.speed_mps,
            "entry_lane_position_metres": state.lane_position_metres,
            "entry_route_index": state.route_index,
            "restriction_activation_observed_while_open": False,
        }

    def _close_lane_visit(
        self, vehicle_id: str, state: VehicleState, start: float, end: float
    ) -> None:
        visit = self.open_lane_visits.pop(vehicle_id)
        visit.update(
            {
                "exit_observed_at_seconds": _number(end),
                "exit_transition_interval_start_seconds": _number(start),
                "exit_transition_interval_end_seconds": _number(end),
                "last_speed_mps": state.speed_mps,
                "last_lane_position_metres": state.lane_position_metres,
                "last_state_observed_at_seconds": _number(start),
                "observed_lane_time_seconds": _number(
                    end - float(visit["entry_observed_at_seconds"])
                ),
            }
        )
        self.lane_visits.setdefault(vehicle_id, []).append(visit)

    def _entry_period(self, visit: Mapping[str, Any]) -> str:
        start = float(visit["entry_transition_interval_start_seconds"])
        end = float(visit["entry_transition_interval_end_seconds"])
        if end <= self.event_start_seconds:
            return "BEFORE"
        if start >= self.event_end_seconds:
            return "AFTER"
        return "DURING"

    def _visit_open_at_activation(self, visit: Mapping[str, Any]) -> bool:
        if visit.get("restriction_activation_observed_while_open") is True:
            return True
        entry = float(visit["entry_observed_at_seconds"])
        exit_time = visit.get("exit_observed_at_seconds")
        return entry <= self.event_start_seconds and (
            exit_time is None or float(exit_time) > self.event_start_seconds
        )

    def _classify_lane_visit(self, visit: Mapping[str, Any]) -> dict[str, Any]:
        classified = dict(visit)
        entry_period = self._entry_period(visit)
        open_at_activation = self._visit_open_at_activation(visit)
        if open_at_activation:
            classification = "PREEXISTING_OCCUPANCY"
        elif entry_period == "DURING":
            classification = "POST_ACTIVATION_ENTRY"
        else:
            classification = f"{entry_period}_EVENT_ENTRY"
        classified.update(
            {
                "entry_period": entry_period,
                "open_at_restriction_activation": open_at_activation,
                "visit_classification": classification,
            }
        )
        return classified

    def finalize(self, final_simulation_time_seconds: float) -> None:
        if self.finalized:
            raise AssertionError("observer already finalized")
        if self.pre_activation_states is None:
            raise AssertionError("pre-activation occupancy snapshot is missing")
        if self.previous_on_edge:
            raise AssertionError(
                f"vehicles remain on monitored edge at cutoff: {sorted(self.previous_on_edge)}"
            )
        if self.open_edge_visits or self.open_lane_visits:
            raise AssertionError("one or more exposure visits remain open at cutoff")
        if self.last_interval_end != float(final_simulation_time_seconds):
            raise AssertionError("observer did not cover the full simulation horizon")
        self.finalized = True

    def pre_activation_payload(self) -> dict[str, Any]:
        if self.pre_activation_states is None:
            raise AssertionError("pre-activation snapshot is unavailable")
        states = [state.payload() for state in self.pre_activation_states]
        return {
            "observer_identity": OBSERVER_IDENTITY,
            "simulation_time_seconds": _number(self.pre_activation_time_seconds),
            "passenger_vehicles": states,
            "lane_occupancy": {
                lane_id: sum(1 for state in states if state["lane_id"] == lane_id)
                for lane_id in self.monitored_lanes
            },
        }

    def events_payload(self) -> dict[str, Any]:
        return {
            "observer_identity": OBSERVER_IDENTITY,
            "run_id": self.run_id,
            "passenger_class": self.passenger_class,
            "monitored_edges": {
                edge: list(lanes) for edge, lanes in self.monitored_edges.items()
            },
            "sampling_step_seconds": 1.0,
            "transition_timestamp_semantics": (
                "Crossing occurred within the recorded half-open/closed one-second "
                "observation interval; observed_at_seconds is its upper endpoint."
            ),
            "events": self.events,
        }

    def summary_payload(self, structural_vehicle_ids: Iterable[str]) -> dict[str, Any]:
        structural_ids = set(str(item) for item in structural_vehicle_ids)
        visits_by_period: dict[str, set[str]] = {
            "BEFORE": set(),
            "DURING": set(),
            "AFTER": set(),
        }
        classified_lane_visits: dict[str, list[dict[str, Any]]] = {
            lane_id: [] for lane_id in self.monitored_lanes
        }
        per_vehicle: dict[str, dict[str, Any]] = {}
        for vehicle_id in sorted(set(self.edge_visits) | structural_ids):
            edge_visits = [dict(visit) for visit in self.edge_visits.get(vehicle_id, [])]
            for visit in edge_visits:
                visit["entry_period"] = self._entry_period(visit)
            periods = sorted({self._entry_period(visit) for visit in edge_visits})
            for period in periods:
                visits_by_period[period].add(vehicle_id)
            lane_visits = [
                self._classify_lane_visit(visit)
                for visit in self.lane_visits.get(vehicle_id, [])
            ]
            for visit in lane_visits:
                classified_lane_visits[visit["lane_id"]].append(visit)
            per_vehicle[vehicle_id] = {
                "structurally_routed_over_monitored_edge": vehicle_id in structural_ids,
                "entry_periods": periods,
                "edge_visits": edge_visits,
                "lane_visits": lane_visits,
                "observed_edge_halting_seconds": self.edge_halting_seconds.get(
                    vehicle_id, 0.0
                ),
            }

        preexisting_lane_users = {
            state.vehicle_id
            for state in (self.pre_activation_states or [])
            if state.lane_id in self.monitored_lanes
        }
        lane_changes = [event for event in self.events if event["event"] == "LANE_CHANGE"]
        lane_visit_diagnostics: dict[str, dict[str, Any]] = {}
        for lane_id, visits in classified_lane_visits.items():
            preexisting = [
                visit
                for visit in visits
                if visit["open_at_restriction_activation"]
            ]
            post_activation_entries = [
                visit for visit in visits if visit["entry_period"] == "DURING"
            ]
            lane_visit_diagnostics[lane_id] = {
                "visit_count": len(visits),
                "visits": visits,
                "preexisting_occupant_ids": sorted(
                    {str(visit["vehicle_id"]) for visit in preexisting}
                ),
                "preexisting_occupant_count": len(
                    {str(visit["vehicle_id"]) for visit in preexisting}
                ),
                "post_activation_entry_ids": sorted(
                    str(visit["vehicle_id"]) for visit in post_activation_entries
                ),
                "post_activation_entry_unique_vehicle_ids": sorted(
                    {str(visit["vehicle_id"]) for visit in post_activation_entries}
                ),
                "post_activation_entry_count": len(post_activation_entries),
                "event_unique_user_ids": sorted(self.event_lane_users[lane_id]),
                "event_unique_user_count": len(self.event_lane_users[lane_id]),
            }
        return {
            "observer_identity": OBSERVER_IDENTITY,
            "run_id": self.run_id,
            "exposure_observability_complete": self.finalized,
            "event_interval_seconds": {
                "start_inclusive": _number(self.event_start_seconds),
                "end_exclusive": _number(self.event_end_seconds),
            },
            "unique_edge_entries": {
                period.lower(): sorted(values)
                for period, values in visits_by_period.items()
            },
            "unique_edge_entry_counts": {
                period.lower(): len(values)
                for period, values in visits_by_period.items()
            },
            "structural_vehicle_count": len(structural_ids),
            "structural_vehicles_never_entering_during_event": sorted(
                structural_ids - visits_by_period["DURING"]
            ),
            "structural_vehicles_never_entering_during_event_count": len(
                structural_ids - visits_by_period["DURING"]
            ),
            "unique_event_edge_users": {
                edge_id: sorted(vehicle_ids)
                for edge_id, vehicle_ids in self.event_edge_users.items()
            },
            "unique_event_lane_users": {
                lane_id: sorted(vehicle_ids)
                for lane_id, vehicle_ids in self.event_lane_users.items()
            },
            "unique_event_lane_user_counts": {
                lane_id: len(vehicle_ids)
                for lane_id, vehicle_ids in self.event_lane_users.items()
            },
            "preexisting_monitored_lane_users": sorted(preexisting_lane_users),
            "preexisting_event_lane_users": {
                lane_id: sorted(vehicle_ids)
                for lane_id, vehicle_ids in self.preexisting_event_lane_users.items()
            },
            "new_event_lane_users": {
                lane_id: sorted(
                    self.event_lane_users[lane_id]
                    - self.preexisting_event_lane_users[lane_id]
                )
                for lane_id in self.monitored_lanes
            },
            "new_event_lane_users_semantics": (
                "Legacy unique-user information only; compliance is determined "
                "from post-activation lane-visit entries."
            ),
            "lane_visit_diagnostics": lane_visit_diagnostics,
            "lane_change_event_count": len(lane_changes),
            "lane_change_events": lane_changes,
            "per_vehicle": per_vehicle,
        }


class ObservedConnection:
    """Transparent connection proxy that surrounds simulationStep with reads."""

    def __init__(self, connection: Any, observer: ExposureObserver) -> None:
        self._connection = connection
        self._observer = observer

    def simulationStep(self, *args: Any, **kwargs: Any) -> Any:
        before = float(self._connection.simulation.getTime())
        self._observer.before_step(self._connection, before)
        result = self._connection.simulationStep(*args, **kwargs)
        after = float(self._connection.simulation.getTime())
        self._observer.after_step(self._connection, before, after)
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)
