"""Offline cutoff/accounting extension; importing this module performs no I/O.

The explicit factory loads only the hash-bound public observer. Its trajectory
logic is reused unchanged; the subclass validates coverage and retains censored
visits. No simulator, process, socket or operational runner is imported.
"""

from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
import sys
import types
from typing import Any


ADAPTER_IDENTITY = "B0_OD_INPUT_AND_CUTOFF_MEASUREMENT_ADAPTER_V2"
OBSERVER_IDENTITY = "B0_CUTOFF_EXPOSURE_OBSERVER_V1"
REVIEWED_OBSERVER_SHA256 = "dd582ab3011d3077c1ad1f63b95f26708813bf0628dcdee4bebda4c054a68d57"
COMPLETED = "COMPLETED"
RIGHT_CENSORED_AT_CUTOFF = "RIGHT_CENSORED_AT_CUTOFF"


class ObservationError(ValueError):
    """An invalid observation is not ordinary cutoff censoring."""


def load_reviewed_observer(observer_path: Path) -> types.ModuleType:
    """Explicitly load verified public bytes, never a historical runner."""
    expected = Path(__file__).resolve().parents[1] / "exposure_observer.py"
    path = Path(observer_path)
    if path.is_symlink() or path.resolve() != expected:
        raise ObservationError("observer dependency is not the exact public path")
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != REVIEWED_OBSERVER_SHA256:
        raise ObservationError("reviewed observer source identity differs")
    name = "_b0_od_adapter_verified_public_observer"
    module = types.ModuleType(name)
    module.__file__ = str(expected)
    # dataclasses resolves its defining module during the verified definition.
    sys.modules[name] = module
    try:
        exec(compile(source, str(expected), "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObservationError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ObservationError(f"{label} must be finite")
    return number


def make_cutoff_observer(
    *, observer_path: Path, horizon_seconds: int = 1500, **observer_kwargs: Any
) -> Any:
    """Build the explicitly versioned observer, with the historical interface."""
    if type(horizon_seconds) is not int or horizon_seconds <= 0:
        raise ObservationError("horizon must be a positive integer")
    historical = load_reviewed_observer(observer_path)

    class CutoffObserver(historical.ExposureObserver):
        def __init__(self) -> None:
            super().__init__(**observer_kwargs)
            if not (
                0 < self.event_start_seconds < self.event_end_seconds < horizon_seconds
                and self.pre_activation_time_seconds == self.event_start_seconds
                and self.event_start_seconds.is_integer()
                and self.event_end_seconds.is_integer()
            ):
                raise ObservationError("event must have integer boundaries inside the horizon")
            if not self.run_id or not self.passenger_class:
                raise ObservationError("run and passenger identities are required")
            if any(not edge or any(not lane for lane in lanes)
                   for edge, lanes in self.monitored_edges.items()):
                raise ObservationError("empty monitored identity")
            self.horizon_seconds = horizon_seconds
            self._expected_time = 0.0
            self._pending_before: float | None = None
            self._observed_steps = 0
            self._invalid = False
            self.cutoff_states: list[dict[str, Any]] = []

        def _require_live(self) -> None:
            if self.finalized or self._invalid:
                raise ObservationError("observer is finalized or has invalid evidence")

        def wrap_connection(self, connection: Any) -> Any:
            return historical.ObservedConnection(connection, self)

        def before_step(self, connection: Any, simulation_time_seconds: float) -> None:
            self._require_live()
            try:
                timestamp = _finite_number(simulation_time_seconds, "before-step time")
                if (self._pending_before is not None or timestamp != self._expected_time
                        or timestamp >= self.horizon_seconds):
                    raise ObservationError("missing, repeated or out-of-order before-step")
                super().before_step(connection, timestamp)
                self._pending_before = timestamp
            except BaseException:
                self._invalid = True
                raise

        def _state(self, connection: Any, vehicle_id: str, edge_id: str | None = None) -> Any:
            state = super()._state(connection, vehicle_id, edge_id)
            if not state.vehicle_id or not state.edge_id or not state.lane_id:
                raise ObservationError("empty vehicle, edge or lane identity")
            if state.vehicle_id != vehicle_id:
                raise ObservationError("state vehicle identity mismatch")
            if (_finite_number(state.speed_mps, "speed") < 0
                    or _finite_number(state.lane_position_metres, "lane position") < 0):
                raise ObservationError("negative speed or lane position")
            if state.route_index is not None and state.route_index < 0:
                raise ObservationError("negative route index")
            previous = self.previous_on_edge.get(vehicle_id)
            if previous is not None and previous.route_index is not None and state.route_index is not None:
                if (state.route_index < previous.route_index
                        or (state.edge_id == previous.edge_id
                            and state.route_index != previous.route_index)):
                    raise ObservationError("inconsistent route occurrence ordering")
            return state

        def after_step(self, connection: Any, start: float, end: float) -> None:
            self._require_live()
            try:
                start = _finite_number(start, "interval start")
                end = _finite_number(end, "interval end")
                if (self._pending_before != start or start != self._expected_time
                        or end != start + 1 or end > self.horizon_seconds):
                    raise ObservationError("trace must contain consecutive one-second steps")
                ids = list(connection.vehicle.getIDList())
                if any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
                    raise ObservationError("invalid or duplicate active vehicle identity")
                super().after_step(connection, start, end)
                self._expected_time = end
                self._pending_before = None
                self._observed_steps += 1
            except BaseException:
                self._invalid = True
                raise

        def _close_edge_visit(self, vehicle_id: str, state: Any, start: float, end: float) -> None:
            super()._close_edge_visit(vehicle_id, state, start, end)
            self.edge_visits[vehicle_id][-1]["visit_status"] = COMPLETED

        def _close_lane_visit(self, vehicle_id: str, state: Any, start: float, end: float) -> None:
            super()._close_lane_visit(vehicle_id, state, start, end)
            self.lane_visits[vehicle_id][-1]["visit_status"] = COMPLETED

        def _validate_end_state(self) -> None:
            ids = set(self.previous_on_edge)
            if ids != set(self.open_edge_visits) or ids != set(self.open_lane_visits):
                raise ObservationError("cutoff state and open visit identities differ")
            for vehicle_id, state in self.previous_on_edge.items():
                edge = self.open_edge_visits[vehicle_id]
                lane = self.open_lane_visits[vehicle_id]
                if (edge["vehicle_id"] != vehicle_id or lane["vehicle_id"] != vehicle_id
                        or state.vehicle_id != vehicle_id or edge["edge_id"] != state.edge_id
                        or lane["edge_id"] != state.edge_id or lane["lane_id"] != state.lane_id
                        or lane["edge_visit_occurrence"] != edge["occurrence_index"]
                        or edge["entry_route_index"] != state.route_index):
                    raise ObservationError("inconsistent cutoff visit identity or occurrence")
                for visit in (edge, lane):
                    start = _finite_number(visit["entry_transition_interval_start_seconds"], "entry start")
                    end = _finite_number(visit["entry_transition_interval_end_seconds"], "entry end")
                    if not (0 <= start < end <= self.horizon_seconds and end == start + 1
                            and end == visit["entry_observed_at_seconds"]):
                        raise ObservationError("impossible open visit entry ordering")
                if lane["entry_observed_at_seconds"] < edge["entry_observed_at_seconds"]:
                    raise ObservationError("lane visit predates its edge visit")
            previous_time = 0.0
            for sequence, event in enumerate(self.events, 1):
                timestamp = _finite_number(event["observed_at_seconds"], "event time")
                start = _finite_number(event["transition_interval_start_seconds"], "event start")
                end = _finite_number(event["transition_interval_end_seconds"], "event end")
                if (event["sequence"] != sequence or timestamp < previous_time
                        or not 0 <= start <= end == timestamp <= self.horizon_seconds):
                    raise ObservationError("inconsistent event ordering")
                previous_time = timestamp

        def finalize(self, final_simulation_time_seconds: float) -> None:
            self._require_live()
            try:
                cutoff = _finite_number(final_simulation_time_seconds, "cutoff")
                if (cutoff != self.horizon_seconds or self._expected_time != cutoff
                        or self.last_interval_end != cutoff or self._pending_before is not None
                        or self._observed_steps != self.horizon_seconds):
                    raise ObservationError("unexpectedly truncated or incomplete observation trace")
                if self.pre_activation_states is None:
                    raise ObservationError("pre-activation snapshot is missing")
                self._validate_end_state()
                self.cutoff_states = [self.previous_on_edge[key].payload()
                                      for key in sorted(self.previous_on_edge)]
                for vehicle_id in sorted(self.previous_on_edge):
                    state = self.previous_on_edge[vehicle_id]
                    for kind, opens, visits in (
                        ("edge", self.open_edge_visits, self.edge_visits),
                        ("lane", self.open_lane_visits, self.lane_visits),
                    ):
                        visit = copy.deepcopy(opens[vehicle_id])
                        followup = historical._number(cutoff - visit["entry_observed_at_seconds"])
                        visit.update({
                            "visit_status": RIGHT_CENSORED_AT_CUTOFF,
                            "exit_observed_at_seconds": None,
                            "exit_transition_interval_start_seconds": None,
                            "exit_transition_interval_end_seconds": None,
                            f"observed_{kind}_time_seconds": None,
                            "observed_followup_seconds": followup,
                            "observed_duration_lower_bound_seconds": followup,
                            "cutoff_seconds": cutoff,
                            "cutoff_state": state.payload(),
                            "last_lane_id": state.lane_id,
                            "last_speed_mps": state.speed_mps,
                            "last_lane_position_metres": state.lane_position_metres,
                            "last_state_observed_at_seconds": cutoff,
                        })
                        visits.setdefault(vehicle_id, []).append(visit)
                self.open_edge_visits.clear()
                self.open_lane_visits.clear()
                self.finalized = True
            except BaseException:
                self._invalid = True
                raise

        def _version(self, payload: dict[str, Any]) -> dict[str, Any]:
            payload["observer_identity"] = OBSERVER_IDENTITY
            return payload

        def events_payload(self) -> dict[str, Any]:
            return self._version(super().events_payload())

        def pre_activation_payload(self) -> dict[str, Any]:
            return self._version(super().pre_activation_payload())

        def summary_payload(self, structural_vehicle_ids: Any) -> dict[str, Any]:
            if not self.finalized or self._invalid:
                raise ObservationError("a complete valid cutoff is required for a summary")
            payload = self._version(super().summary_payload(structural_vehicle_ids))
            payload["cutoff_seconds"] = float(self.horizon_seconds)
            payload["cutoff_monitored_states"] = copy.deepcopy(self.cutoff_states)
            payload["all_monitored_visits_completed"] = not self.cutoff_states
            return payload

    return CutoffObserver()

# Pure structured-record adaptation; no simulator imports or operational driver.
import xml.etree.ElementTree as _ET


def _account_number(value):
    import math
    if isinstance(value, bool):
        raise ValueError("boolean is not a numeric observation")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite observation")
    return number


def parse_tripinfo_xml(xml_data):
    """Parse supplied XML only, preserving raw attributes and duplicate evidence.

    Negative depart/arrival values are interpreted later as unavailable, matching
    the published B0 parser. There is no declared negative waitingTime sentinel.
    """
    root = _ET.fromstring(xml_data)
    if root.tag != "tripinfos" or any(node.tag != "tripinfo" for node in root):
        raise ValueError("expected tripinfos containing only tripinfo records")
    records = [dict(node.attrib) for node in root]
    ids = [row.get("id") for row in records]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("missing or duplicate tripinfo IDs")
    return records


def account_trips(
    scheduled, *, tripinfo_records, departed_events, arrival_events,
    cutoff_active_ids, cutoff_pending_ids, per_trip_halting_seconds, queue_trace,
    teleport_start_events=None, teleport_end_events=None,
    observations_complete=True, final_time_seconds=1500,
):
    """Reconcile supplied observations, not infer never-departure from tripinfo.

    A smaller supplied population is allowed for synthetic fixtures only; the
    OD-input validator separately enforces the live protocol's exact 540 trips.
    Only VALID results may feed qualification. Deficient records retain raw
    evidence and all scheduled ledger rows, with no zero imputation for departed
    native waiting. Queue/halting uses the inherited one-second, speed<0.1 rule.
    """
    horizon = 1500
    errors, deficient = [], []
    if observations_complete is not True or final_time_seconds != horizon:
        errors.append("INCOMPLETE_OBSERVATION_HORIZON")
    trips = {}
    for row in scheduled:
        vehicle_id = row.get("vehicle_id")
        if not isinstance(vehicle_id, str) or not vehicle_id or vehicle_id in trips:
            raise ValueError("missing or duplicate scheduled ID")
        departure = _account_number(row["scheduled_departure_seconds"])
        if not 0 <= departure < 900 or not isinstance(row.get("route_id"), str):
            raise ValueError("invalid scheduled departure or route")
        trips[vehicle_id] = dict(row)
    if not trips:
        raise ValueError("empty scheduled population")
    ids = set(trips)
    raw = {}
    for row in tripinfo_records:
        vehicle_id = row.get("id")
        if not isinstance(vehicle_id, str) or not vehicle_id or vehicle_id in raw:
            raise ValueError("missing or duplicate tripinfo ID")
        raw[vehicle_id] = dict(row)
    if set(raw) - ids:
        errors.append("UNKNOWN_TRIPINFO_IDS")
    def id_set(values, label):
        values = list(values)
        if any(not isinstance(v, str) for v in values):
            raise ValueError("invalid ID in " + label)
        if len(values) != len(set(values)):
            errors.append("DUPLICATE_IDS:" + label)
        if set(values) - ids:
            errors.append("UNKNOWN_IDS:" + label)
        return set(values) & ids
    def events(value, label):
        found = id_set(value, label)
        for vehicle_id, times in value.items():
            if not isinstance(times, (list, tuple)) or len(times) != 1:
                errors.append("MISSING_OR_DUPLICATE_EVENT:" + label + ":" + vehicle_id)
                continue
            try:
                timestamp = _account_number(times[0])
                if not 1 <= timestamp <= horizon or not timestamp.is_integer():
                    raise ValueError()
            except (TypeError, ValueError):
                errors.append("INVALID_EVENT_TIME:" + label + ":" + vehicle_id)
        return found
    departures = events(departed_events, "departure")
    arrivals = events(arrival_events, "arrival")
    teleport_start_events = {} if teleport_start_events is None else teleport_start_events
    teleport_end_events = {} if teleport_end_events is None else teleport_end_events
    teleports = events(teleport_start_events, "teleport_start")
    ends = events(teleport_end_events, "teleport_end")
    active = id_set(cutoff_active_ids, "active")
    pending = id_set(cutoff_pending_ids, "pending")
    if teleports or ends:
        errors.append("TELEPORT_GUARDRAIL_FAILURE")
    if ends - teleports:
        errors.append("TELEPORT_END_WITHOUT_START")
    if active & pending or active & arrivals or pending & arrivals:
        errors.append("CONTRADICTORY_CUTOFF_MEMBERSHIP")
    if (active | arrivals | teleports) - departures:
        errors.append("MISSING_DEPARTURE_OBSERVATION")
    for vehicle_id in arrivals & departures:
        try:
            if _account_number(arrival_events[vehicle_id][0]) < _account_number(departed_events[vehicle_id][0]):
                errors.append("EVENT_ARRIVAL_PRECEDES_DEPARTURE:" + vehicle_id)
        except (ValueError, TypeError, IndexError):
            pass  # Event schema failure is already recorded.
    categories = {
        "teleported": teleports,
        "arrived": arrivals - teleports,
        "active": active - teleports - arrivals,
        "not_departed": pending - departures - teleports - arrivals - active,
    }
    categories["failed_invalid"] = ids - set().union(*categories.values())
    if categories["failed_invalid"]:
        errors.append("UNEXPLAINED_DISAPPEARANCE")
    if sum(map(len, categories.values())) != len(ids):
        errors.append("NON_DISJOINT_TERMINAL_PARTITION")
    ledger, restricted = {}, []
    waiting_total, waiting_bad = 0.0, False
    for vehicle_id in sorted(ids):
        category = next(k for k, members in categories.items() if vehicle_id in members)
        row = raw.get(vehicle_id)
        scheduled_time = _account_number(trips[vehicle_id]["scheduled_departure_seconds"])
        def timestamp(field):
            value = None if row is None else row.get(field)
            if value is None:
                return None
            try:
                value = _account_number(value)
            except (TypeError, ValueError):
                errors.append("INVALID_TRIPINFO_TIME:" + vehicle_id + ":" + field)
                return None
            return None if value < 0 else value
        actual, arrival = timestamp("depart"), timestamp("arrival")
        if actual is not None and (actual < scheduled_time or actual > horizon):
            errors.append("DEPARTURE_TIME_CONTRADICTION:" + vehicle_id)
        if actual is not None and vehicle_id not in departures:
            errors.append("UNOBSERVED_RECORDED_DEPARTURE:" + vehicle_id)
        if arrival is not None and (actual is None or arrival < actual or arrival > horizon):
            errors.append("ARRIVAL_TIME_CONTRADICTION:" + vehicle_id)
        if arrival is not None and vehicle_id not in arrivals:
            errors.append("UNOBSERVED_RECORDED_ARRIVAL:" + vehicle_id)
        for field, recorded, event_map in (
            ("departure", actual, departed_events), ("arrival", arrival, arrival_events)
        ):
            times = event_map.get(vehicle_id, [])
            if recorded is not None and len(times) == 1:
                try:
                    upper = _account_number(times[0])
                    if not upper - 1 <= recorded <= upper:
                        errors.append("EVENT_TRIPINFO_TIME_CONTRADICTION:" + field + ":" + vehicle_id)
                except (TypeError, ValueError):
                    pass  # Invalid event already reported above.
        if vehicle_id in departures and actual is None:
            deficient.append("DEPARTED_ACTUAL_TIME_UNAVAILABLE:" + vehicle_id)
        valid_arrival = arrival if category == "arrived" and actual is not None else None
        if category == "arrived" and valid_arrival is None:
            deficient.append("ARRIVAL_TIME_UNAVAILABLE:" + vehicle_id)
        value = (horizon if valid_arrival is None else min(valid_arrival, horizon)) - scheduled_time
        if not 0 <= value <= horizon - scheduled_time:
            errors.append("INVALID_RESTRICTED_TIME:" + vehicle_id)
        restricted.append(value)
        raw_wait = None if row is None else row.get("waitingTime")
        normalized_wait, wait_reason = None, "VALID_NATIVE_WAITING"
        proven_undeparted = (
            category == "not_departed" and observations_complete is True
            and final_time_seconds == horizon and actual is None and arrival is None
        )
        if raw_wait is None:
            if proven_undeparted:
                normalized_wait, wait_reason = 0.0, "PROVEN_UNDEPARTED_ZERO_BY_CONTRACT"
            else:
                wait_reason = "NATIVE_WAITING_MISSING"
        else:
            try:
                supplied_wait = _account_number(raw_wait)
                if supplied_wait < 0:
                    wait_reason = "NEGATIVE_WAITING_NOT_A_DECLARED_SENTINEL"
                elif proven_undeparted:
                    if supplied_wait == 0:
                        normalized_wait, wait_reason = 0.0, "PROVEN_UNDEPARTED_ZERO_BY_CONTRACT"
                    else:
                        errors.append("UNDEPARTED_POSITIVE_WAITING:" + vehicle_id)
                        wait_reason = "CONTRADICTORY_UNDEPARTED_WAITING"
                else:
                    normalized_wait = supplied_wait
            except (TypeError, ValueError):
                wait_reason = "INVALID_NATIVE_WAITING"
        if normalized_wait is None:
            waiting_bad = True
            deficient.append(wait_reason + ":" + vehicle_id)
        else:
            waiting_total += normalized_wait
        ledger[vehicle_id] = {
            "route_id": trips[vehicle_id]["route_id"],
            "scheduled_departure_seconds": scheduled_time,
            "actual_departure_seconds": actual,
            "valid_non_teleported_arrival_seconds": valid_arrival,
            "terminal_category": category,
            "restricted_trip_time_seconds": value,
            "departure_delay_seconds": None if actual is None else actual - scheduled_time,
            "native_waiting_normalized_seconds": normalized_wait,
            "native_waiting_interpretation": wait_reason,
            "raw_tripinfo": row,
            "pending_at_cutoff": vehicle_id in pending,
            "teleport_event": vehicle_id in teleports,
        }
    # Individually finite waits can overflow binary-float addition. Preserve
    # every ledger row, but never expose an overflow or partial sum as a total.
    if not math.isfinite(waiting_total):
        errors.append("AGGREGATE_NATIVE_WAITING_NONFINITE")
        waiting_bad = True
    queue_total = None
    try:
        rows = list(queue_trace)
        if len(rows) != horizon or any(
            len(row) != 2 or row[0] != i
            or isinstance(row[0], bool)
            or not 0 <= _account_number(row[1]) <= len(ids)
            or _account_number(row[1]) != int(_account_number(row[1]))
            for i, row in enumerate(rows, 1)
        ):
            raise ValueError()
        queue_total = sum(_account_number(row[1]) for row in rows)
        if not errors:
            for time, count_at_time in rows:
                possible_active = sum(
                    departed_events[v][0] <= time
                    and (v not in arrivals or time < arrival_events[v][0])
                    for v in departures
                )
                if count_at_time > possible_active:
                    raise ValueError("queue exceeds observed active population")
    except (ValueError, TypeError, OverflowError):
        errors.append("INVALID_OR_TRUNCATED_QUEUE_TRACE")
    try:
        if set(per_trip_halting_seconds) != ids:
            raise ValueError()
        halting = {key: _account_number(value) for key, value in per_trip_halting_seconds.items()}
        if any(value < 0 or value > horizon or value != int(value) for value in halting.values()):
            raise ValueError()
        if any(halting[v] != 0 for v in categories["not_departed"]):
            raise ValueError()
        if not errors:
            for vehicle_id in departures:
                last_exclusive = arrival_events[vehicle_id][0] if vehicle_id in arrivals else horizon + 1
                if halting[vehicle_id] > last_exclusive - departed_events[vehicle_id][0]:
                    raise ValueError("halting exceeds observed sampled lifetime")
        if queue_total is not None and sum(halting.values()) != queue_total:
            raise ValueError()
        for vehicle_id, value in halting.items():
            ledger[vehicle_id]["observed_halting_seconds"] = value
    except (TypeError, ValueError):
        errors.append("INVALID_OR_INCOMPLETE_CUSTOM_HALTING")
    count = len(ids)
    arrived_count = len(categories["arrived"])
    metrics = {
        "scheduled_trips": count,
        "arrived_trips": arrived_count,
        "active_trips_at_cutoff": len(categories["active"]),
        "not_departed_trips_at_cutoff": len(categories["not_departed"]),
        "teleported_terminal_trips": len(categories["teleported"]),
        "failed_invalid_trips": len(categories["failed_invalid"]),
        "unfinished_trips": count - arrived_count,
        "completion_fraction": arrived_count / count,
        "restricted_mean_trip_time_seconds": sum(restricted) / count,
        "restricted_p95_trip_time_seconds_nearest_rank": sorted(restricted)[(95 * count + 99) // 100 - 1],
        "sumo_tripinfo_waiting_time_seconds_total": None if waiting_bad else waiting_total,
        "cumulative_queue_vehicle_seconds": queue_total,
        "custom_queue_halting_speed_threshold_mps": 0.1,
    }
    # The other metrics have bounded inputs or exact integer arithmetic; still
    # enforce finiteness at the returned metric boundary, including invalid runs.
    for name, value in metrics.items():
        if isinstance(value, float) and not math.isfinite(value):
            errors.append("AGGREGATE_METRIC_NONFINITE:" + name)
            metrics[name] = None
    return {
        "measurement_status": "INTEGRITY_FAILURE" if errors else "EVIDENCE_DEFICIENCY" if deficient else "VALID",
        "integrity_errors": sorted(set(errors)),
        "evidence_deficiencies": sorted(set(deficient)),
        "ledger": ledger, "metrics": metrics,
        "qualification_evaluated": False,
    }


def completion_gate(arrived_count, scheduled_count, condition):
    """Exact inherited inclusive completion gate, separate from validity."""
    if (
        type(arrived_count) is not int or type(scheduled_count) is not int
        or not 0 <= arrived_count <= scheduled_count or scheduled_count <= 0
        or condition not in ("N0", "D0")
    ):
        raise ValueError("invalid completion-gate inputs")
    return 100 * arrived_count >= (99 if condition == "N0" else 95) * scheduled_count


def paired_local_response(n0_summary, d0_summary, n0_ledger, d0_ledger):
    """Pure conservative V1 local witness reader. Never infer from censoring bounds."""
    try:
        if any(
            s.get("observer_identity") != OBSERVER_IDENTITY
            or s.get("cutoff_seconds") != 1500
            or s.get("exposure_observability_complete") is not True
            for s in (n0_summary, d0_summary)
        ):
            raise ValueError("incomplete or incompatible summary")
        exposed = d0_summary["unique_edge_entries"]["during"]
        if not isinstance(exposed, list) or any(not isinstance(v, str) for v in exposed):
            raise ValueError()
        if len(exposed) != len(set(exposed)):
            raise ValueError()
        if not isinstance(d0_summary["per_vehicle"], dict) or not isinstance(n0_summary["per_vehicle"], dict):
            raise ValueError()
        if d0_summary["unique_edge_entry_counts"]["during"] != len(exposed):
            raise ValueError("exposure count mismatch")
        observed_ids = {
            key for key, record in d0_summary["per_vehicle"].items()
            if any(v["edge_id"] == "A1B1" and v["entry_period"] == "DURING"
                   for v in record["edge_visits"])
        }
        if observed_ids != set(exposed):
            raise ValueError("exposure list and visits disagree")
    except (KeyError, TypeError, ValueError):
        return {"status": "NOT_IDENTIFIABLE", "local_physical_response_observed": None,
                "comparisons": [], "vehicles_with_local_physical_response": [],
                "unidentifiable_comparisons": ["MALFORMED_EXPOSURE_SUMMARY"]}
    comparisons, unknown, witnesses = [], [], []
    def unique_visit(summary, vehicle_id, during):
        try:
            visits = [v for v in summary["per_vehicle"][vehicle_id]["edge_visits"] if v["edge_id"] == "A1B1"]
            if len(visits) != 1 or (during and visits[0]["entry_period"] != "DURING"):
                return None
            return visits[0]
        except (KeyError, TypeError):
            return None
    def validate_visit(visit, vehicle_id, during):
        if visit["vehicle_id"] != vehicle_id or type(visit["occurrence_index"]) is not int or visit["occurrence_index"] != 0:
            raise ValueError("invalid vehicle/occurrence identity")
        entry = _account_number(visit["entry_observed_at_seconds"])
        start = _account_number(visit["entry_transition_interval_start_seconds"])
        end = _account_number(visit["entry_transition_interval_end_seconds"])
        if not 1 <= entry <= 1500 or not entry.is_integer() or start != entry - 1 or end != entry:
            raise ValueError("invalid entry interval")
        if during and not (end > 300 and start < 600):
            raise ValueError("event entry is outside the event window")
        halting = _account_number(visit["observed_halting_seconds"])
        if halting < 0 or not halting.is_integer():
            raise ValueError("invalid observed halting")
        if visit["visit_status"] == COMPLETED:
            exit_time = _account_number(visit["exit_observed_at_seconds"])
            duration = _account_number(visit["observed_edge_time_seconds"])
            if (not exit_time.is_integer() or not entry < exit_time <= 1500
                    or visit["exit_transition_interval_end_seconds"] != exit_time
                    or visit["exit_transition_interval_start_seconds"] != exit_time - 1
                    or duration != exit_time - entry or halting > duration):
                raise ValueError("invalid completed interval or duration")
        else:
            if (any(visit[key] is not None for key in (
                    "exit_observed_at_seconds", "exit_transition_interval_start_seconds",
                    "exit_transition_interval_end_seconds", "observed_edge_time_seconds"))
                    or visit["cutoff_seconds"] != 1500
                    or visit["observed_followup_seconds"] != 1500 - entry
                    or visit["observed_duration_lower_bound_seconds"] != 1500 - entry
                    or halting > 1500 - entry + 1):
                raise ValueError("invalid censored followup")
    for vehicle_id in exposed:
        nv = unique_visit(n0_summary, vehicle_id, False)
        dv = unique_visit(d0_summary, vehicle_id, True)
        if nv is None or dv is None:
            unknown.append({"vehicle_id": vehicle_id, "reason": "MISSING_OR_NON_UNIQUE_A1B1_VISIT"})
            continue
        try:
            nl, dl = n0_ledger[vehicle_id], d0_ledger[vehicle_id]
            if (nl["route_id"], nl["scheduled_departure_seconds"]) != (dl["route_id"], dl["scheduled_departure_seconds"]):
                raise ValueError("pair input mismatch")
            if nl["route_id"] != "row1_east":
                raise ValueError("invalid target route")
        except (KeyError, TypeError, ValueError):
            unknown.append({"vehicle_id": vehicle_id, "reason": "MISSING_OR_INCONSISTENT_PAIRED_LEDGER"})
            continue
        if any(v.get("visit_status") not in (COMPLETED, RIGHT_CENSORED_AT_CUTOFF) for v in (nv, dv)):
            unknown.append({"vehicle_id": vehicle_id, "reason": "INVALID_VISIT_STATUS"})
            continue
        time_delta = halting_delta = arrival_delta = None
        try:
            validate_visit(nv, vehicle_id, False)
            validate_visit(dv, vehicle_id, True)
            for visit, record in ((nv, nl), (dv, dl)):
                category = record["terminal_category"]
                arrival = record["valid_non_teleported_arrival_seconds"]
                if category not in ("arrived", "active"):
                    raise ValueError("exposed trip has invalid terminal category")
                if category == "arrived":
                    arrival = _account_number(arrival)
                    if (visit["visit_status"] != COMPLETED
                            or not record["scheduled_departure_seconds"] <= arrival <= 1500
                            or arrival < visit["exit_transition_interval_start_seconds"]):
                        raise ValueError("contradictory valid arrival")
                elif arrival is not None:
                    raise ValueError("active trip cannot have a valid arrival")
            if nv.get("visit_status") == dv.get("visit_status") == "COMPLETED":
                nd, dd = _account_number(nv["observed_edge_time_seconds"]), _account_number(dv["observed_edge_time_seconds"])
                nh, dh = _account_number(nv["observed_halting_seconds"]), _account_number(dv["observed_halting_seconds"])
                if min(nd, dd, nh, dh) < 0:
                    raise ValueError()
                time_delta, halting_delta = dd - nd, dh - nh
            if nl["terminal_category"] == dl["terminal_category"] == "arrived":
                na = _account_number(nl["valid_non_teleported_arrival_seconds"])
                da = _account_number(dl["valid_non_teleported_arrival_seconds"])
                if not nl["scheduled_departure_seconds"] <= na <= 1500 or not dl["scheduled_departure_seconds"] <= da <= 1500:
                    raise ValueError()
                # An open visit at H and a claimed valid arrival cannot coexist.
                if "RIGHT_CENSORED_AT_CUTOFF" in (nv.get("visit_status"), dv.get("visit_status")):
                    raise ValueError()
                arrival_delta = da - na
        except (KeyError, TypeError, ValueError):
            unknown.append({"vehicle_id": vehicle_id, "reason": "INVALID_OR_UNAVAILABLE_COMPARISON"})
            time_delta = halting_delta = arrival_delta = None
        positive = any(v is not None and v > 0 for v in (time_delta, halting_delta, arrival_delta))
        comparisons.append({
            "vehicle_id": vehicle_id, "edge_time_delta_seconds": time_delta,
            "edge_halting_delta_seconds": halting_delta,
            "final_arrival_delta_seconds": arrival_delta, "local_physical_response": positive,
        })
        if positive:
            witnesses.append(vehicle_id)
        elif any(v is None for v in (time_delta, halting_delta, arrival_delta)):
            unknown.append({"vehicle_id": vehicle_id, "reason": "NO_WITNESS_AND_COMPARISON_UNAVAILABLE"})
    status = "PASS" if witnesses else "NOT_IDENTIFIABLE" if unknown else "FAIL"
    return {
        "status": status, "exposed_vehicle_count": len(exposed), "exposed_vehicle_ids": exposed,
        "comparisons": comparisons, "unidentifiable_comparisons": unknown,
        "vehicles_with_local_physical_response": witnesses,
        "local_physical_response_observed": True if witnesses else None if unknown else False,
    }
