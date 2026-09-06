"""Explicit input and observation binding; no simulator import or launcher.

The connection is already supplied by the caller. The collector supplies raw
scientific-setting/TLS definitions and interval diagnostics, and reads output
only after close. These interfaces are exercised with fake backends here; their
thin live implementation and actual simulator semantics remain unvalidated.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.b0.od_concentration_v2 import od_input, cutoff_measurement as adapter

IDENTITY = "B0_OD_INTEGRATION_LAYER_V1"
IMPLEMENTATION_BASE = "b9cccd5cf8fe129711e6e9b36089312525e1fc01"
PUBLIC_HASHES = {
    "scripts/b0/od_concentration_v2/od_input.py": "b78482335713b029eba50c62eb1f3a3a1976399ededf3bf749ab49e91a5db8a3",
    "scripts/b0/od_concentration_v2/cutoff_measurement.py": "88dcdeafd174392758d74cc62a3ca3932632692248b620d1955d9df0442938cb",
}
RUN_KEYS = {"schema_version", "integration_identity", "evidence_kind", "ready_to_run",
            "run_id", "condition_label", "binding", "observations", "summary", "events",
            "preactivation", "lifecycle", "controls", "failure", "cleanup_failures",
            "output_finalized", "measurement"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def repository_root():
    return Path(od_input.__file__).resolve().parents[3]


def contract():
    return od_input.load_contract(repository_root() / "configs/b0/od-concentration-v1/calibration-contract.json")


def build_binding(repo_root, seed, level):
    root = Path(repo_root)
    if root.is_symlink() or root.resolve() != repository_root():
        raise ValueError("UNREVIEWED_REPOSITORY_ROOT")
    frozen = contract()
    dependencies = dict(PUBLIC_HASHES)
    dependencies.update({v["path"]: v["sha256"] for v in frozen["source_bindings"].values()
                         if isinstance(v, dict) and "path" in v and "sha256" in v})
    dependencies[frozen["source_repository"]["inherited_contract_path"]] = frozen["source_repository"]["inherited_contract_sha256"]
    for name, expected in dependencies.items():
        path = root / name
        if any(p.is_symlink() for p in (path, *path.parents)) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("REVIEWED_DEPENDENCY_CHANGED")
    trips = od_input.build_seed_allocations(frozen, seed)[level] if level in frozen["selection_rule"]["sequence"] else ()
    report = od_input.validate_allocation(frozen, seed, level, trips)
    raw = od_input.serialize_routes(frozen, seed, level, trips) + b"\n"
    report_xml = od_input.validate_routes_xml(frozen, seed, level, raw)
    return {
        "seed": seed, "level": level, "contract_identity": frozen["contract_identity"],
        "contract_sha256": od_input.CONTRACT_SHA256,
        "source_repository_historical_commit": frozen["source_repository"]["commit"],
        "implementation_repository_commit": IMPLEMENTATION_BASE,
        "dependency_sha256": dependencies,
        "implementation_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(Path(__file__).parent.glob("*.py"))},
        "id_departure_vector_sha256": report["id_departure_vector_sha256"],
        "logical_assignment_sha256": report["logical_assignment_sha256"],
        "route_file_sha256": report_xml["xml_sha256"],
        "scientific_configuration": frozen["scientific_configuration"],
    }


def checked_binding(binding):
    if not isinstance(binding, dict) or binding != build_binding(repository_root(), binding.get("seed"), binding.get("level")):
        raise ValueError("RUN_INPUT_OR_SOURCE_BINDING_CHANGED")
    return contract()


def scheduled(binding):
    frozen = checked_binding(binding)
    return [dict(vehicle_id=t.vehicle_id, scheduled_departure_seconds=t.scheduled_departure_seconds,
                 route_id=t.route_id) for t in od_input.build_seed_allocations(frozen, binding["seed"])[binding["level"]]]


def materialize_input(binding, output_dir):
    from .evidence import write_input_once, readback
    frozen = checked_binding(binding)
    trips = od_input.build_seed_allocations(frozen, binding["seed"])[binding["level"]]
    raw = od_input.serialize_routes(frozen, binding["seed"], binding["level"], trips) + b"\n"
    def validator(data):
        result = od_input.validate_routes_xml(frozen, binding["seed"], binding["level"], data)
        if data != raw or result["xml_sha256"] != binding["route_file_sha256"]:
            raise ValueError("INPUT_READBACK_MISMATCH")
    receipt = write_input_once(output_dir, f"{binding['seed']}-{binding['level']}.rou.xml", raw, validator)
    if readback(receipt, validator=validator) != raw:
        raise ValueError("INPUT_READBACK_MISMATCH")
    return receipt


def expected_controls(binding):
    """Raw static TLS definitions from the exact reviewed network, not a second table."""
    checked_binding(binding)
    network = ET.fromstring((repository_root() / "configs/b0/b0-grid-3x3-v1/b0-grid-3x3.net.xml").read_bytes())
    return {"scientific_configuration": copy.deepcopy(binding["scientific_configuration"]),
            "input_identity": {"seed": binding["seed"], "level": binding["level"],
                "route_file_sha256": binding["route_file_sha256"],
                "logical_assignment_sha256": binding["logical_assignment_sha256"],
                "id_departure_vector_sha256": binding["id_departure_vector_sha256"],
                "network_sha256": binding["dependency_sha256"]["configs/b0/b0-grid-3x3-v1/b0-grid-3x3.net.xml"],
                "original_configuration_sha256": binding["dependency_sha256"]["configs/b0/b0-grid-3x3-v1/b0.sumocfg"]},
            "tls": [{"attributes": dict(node.attrib), "phases": [dict(p.attrib) for p in node]}
                    for node in network.findall("tlLogic")]}


class ReadOnlyConnection:
    """Narrow read surface handed to the observer/collector, never to setters."""
    _GETTERS = {
        "simulation": {"getTime", "getDeltaT", "getDepartedIDList", "getArrivedIDList",
                       "getStartingTeleportIDList", "getEndingTeleportIDList", "getPendingVehicles"},
        "vehicle": {"getIDList", "getVehicleClass", "getRoadID", "getLaneID", "getSpeed",
                    "getLanePosition", "getRouteIndex", "getRoute"},
        "lane": {"getAllowed", "getDisallowed", "getLastStepVehicleIDs"},
        "trafficlight": {"getIDList", "getProgram", "getAllProgramLogics", "getRedYellowGreenState"},
    }
    class Domain:
        def __init__(self, target, allowed):
            self._target, self._allowed = target, allowed
        def __getattr__(self, name):
            if name not in self._allowed:
                raise ValueError("UNEXPECTED_CONNECTION_MEMBER")
            return getattr(self._target, name)
    def __init__(self, connection):
        for name, methods in self._GETTERS.items():
            if hasattr(connection, name):
                setattr(self, name, self.Domain(getattr(connection, name), methods))


def _permissions(view, lanes):
    return {lane: {"allowed": sorted(view.lane.getAllowed(lane)),
                   "disallowed": sorted(view.lane.getDisallowed(lane))} for lane in lanes}


def _allowed(p, passenger):
    return (not p["allowed"] or passenger in p["allowed"]) and passenger not in p["disallowed"]


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("NONFINITE_OR_INVALID_OBSERVATION")
    return value


def _observer(binding, run_id):
    cfg = binding["scientific_configuration"]
    return adapter.make_cutoff_observer(observer_path=repository_root()/"scripts/b0/exposure_observer.py",
        run_id=run_id, monitored_edges={cfg["monitored_edge"]: [cfg["restricted_lane"], cfg["surviving_lane"]]},
        passenger_class=cfg["passenger_class"], event_start_seconds=cfg["disruption_start_inclusive"],
        event_end_seconds=cfg["disruption_end_exclusive"], pre_activation_time_seconds=cfg["disruption_start_inclusive"])


def _monitor_states(view, active, observer, monitored_edge):
    states = {}
    for vehicle_id in active:
        edge = view.vehicle.getRoadID(vehicle_id)
        if edge != monitored_edge and vehicle_id not in observer.previous_on_edge:
            continue
        try:
            route_index = view.vehicle.getRouteIndex(vehicle_id)
        except (AttributeError, NotImplementedError):
            route_index = None
        states[vehicle_id] = dict(edge=edge, lane=view.vehicle.getLaneID(vehicle_id),
            speed=view.vehicle.getSpeed(vehicle_id), position=view.vehicle.getLanePosition(vehicle_id),
            route_index=route_index)
    return states


def _replay_exposure(record):
    """Reconstruct the real observer's output from retained sampled raw states."""
    binding = record["binding"]; cfg = binding["scientific_configuration"]
    observer = _observer(binding, record["run_id"])

    class Replay:
        def __init__(self):
            self.sample = None
            self.vehicle = self.lane = self
        def getIDList(self):
            return self.sample["active_ids"]
        def getVehicleClass(self, vehicle_id):
            return cfg["passenger_class"]
        def getRoadID(self, vehicle_id):
            state = self.sample["monitor_states"].get(vehicle_id)
            return "_UNMONITORED_" if state is None else state["edge"]
        def getLaneID(self, vehicle_id):
            return self.sample["monitor_states"][vehicle_id]["lane"]
        def getSpeed(self, vehicle_id):
            return self.sample["monitor_states"][vehicle_id]["speed"]
        def getLanePosition(self, vehicle_id):
            return self.sample["monitor_states"][vehicle_id]["position"]
        def getRouteIndex(self, vehicle_id):
            value = self.sample["monitor_states"][vehicle_id]["route_index"]
            if value is None:
                raise NotImplementedError()
            return value
        def getAllowed(self, lane):
            return self.sample["permissions"][lane]["allowed"]
        def getDisallowed(self, lane):
            return self.sample["permissions"][lane]["disallowed"]

    replay = Replay()
    for start, sample in enumerate(record["controls"]["steps"]):
        states = sample["monitor_states"]; active = set(sample["active_ids"])
        if (not isinstance(states, dict) or set(states) - active
                or (set(observer.previous_on_edge) & active) - set(states)):
            raise ValueError("MONITOR_STATE_COVERAGE")
        for vehicle_id, state in states.items():
            if (not isinstance(state, dict) or set(state) != {"edge", "lane", "speed", "position", "route_index"}
                    or (state["edge"] != cfg["monitored_edge"] and vehicle_id not in observer.previous_on_edge)):
                raise ValueError("MONITOR_STATE_SCHEMA")
            if (_number(state["speed"]) < 0
                    or (_number(state["speed"]) < 0.1) != (vehicle_id in sample["halting_ids"])):
                raise ValueError("MONITOR_HALTING_MISMATCH")
        replay.sample = sample
        observer.before_step(replay, start)
        observer.after_step(replay, start, sample["time"])
    observer.finalize(cfg["h_pilot_seconds"])
    routes = {r["id"]: r["edges"].split() for r in cfg["route_definitions"]}
    structural = [r["vehicle_id"] for r in scheduled(binding)
                  if cfg["monitored_edge"] in routes[r["route_id"]]]
    if (observer.events_payload() != record["events"]
            or observer.summary_payload(structural) != record["summary"]
            or observer.pre_activation_payload() != record["preactivation"]):
        raise ValueError("EXPOSURE_REPLAY_MISMATCH")


def observe_run(binding, condition_label, run_id, connection, collector):
    """Observe one supplied connection, always without retry or a launch operation.

    collector.controls(read_only_connection) returns expected_controls-shaped
    raw definitions/settings and identity of the inputs actually configured and
    read back by its backend. A live collector must derive that evidence from
    the actual loaded inputs, never echo this expected binding. Its live mapping
    remains a separate unvalidated task. collector.diagnostics returns counts.
    collector.finalize_output() is called only after attempted connection close,
    and returns complete supplied tripinfo XML or raises an evidence error.
    """
    frozen = checked_binding(binding)
    if condition_label not in ("N0", "D0", "N0-CAL-R", "D0-CAL-R") or not isinstance(run_id, str) or not run_id:
        raise ValueError("RUN_IDENTITY")
    cfg = binding["scientific_configuration"]
    role = condition_label.split("-")[0]
    rows = scheduled(binding); ids = {r["vehicle_id"] for r in rows}
    routes = {r["id"]: tuple(r["edges"].split()) for r in cfg["route_definitions"]}
    route_for = {r["vehicle_id"]: routes[r["route_id"]] for r in rows}
    obs = dict(tripinfo_records=[], departed_events={}, arrival_events={}, cutoff_active_ids=[],
               cutoff_pending_ids=[], per_trip_halting_seconds={i: 0 for i in sorted(ids)},
               queue_trace=[], teleport_start_events={}, teleport_end_events={},
               observations_complete=False, final_time_seconds=0, step_intervals=[])
    record = dict(schema_version=1, integration_identity=IDENTITY, evidence_kind="SYNTHETIC",
                  ready_to_run=False, run_id=run_id, condition_label=condition_label,
                  binding=copy.deepcopy(binding), observations=obs, summary=None, events=None,
                  preactivation=None, lifecycle=[], controls={"initial": None, "steps": [], "final": None,
                  "permissions_initial": None, "permissions_final": None}, failure=None,
                  cleanup_failures=[], output_finalized=False, measurement=None)
    view = observer = None
    baseline = None; mutation_attempted = False; restored = False; stage = "INITIAL_STATE"
    lanes = [cfg["restricted_lane"], cfg["surviving_lane"]]
    try:
        view = ReadOnlyConnection(connection)
        observer = _observer(binding, run_id)
        expected = expected_controls(binding); controls_sha = digest(expected)
        if view.simulation.getTime() != 0 or view.simulation.getDeltaT() != cfg["simulation_step_seconds"]:
            raise ValueError("INITIAL_CLOCK")
        baseline = _permissions(view, lanes)
        record["controls"]["permissions_initial"] = baseline
        if not all(_allowed(p, cfg["passenger_class"]) for p in baseline.values()):
            raise ValueError("INITIAL_PERMISSION")
        record["controls"]["initial"] = copy.deepcopy(collector.controls(view))
        if record["controls"]["initial"] != expected:
            raise ValueError("SCIENTIFIC_CONTROLS_CHANGED")
        for start in range(cfg["h_pilot_seconds"]):
            stage = "CLOCK"
            if view.simulation.getTime() != start:
                raise ValueError("MISSING_OR_DUPLICATE_STEP")
            if role == "D0" and start in (cfg["disruption_start_inclusive"], cfg["disruption_end_exclusive"]):
                stage = "PERMISSION_OPERATION"
                before = _permissions(view, lanes)
                mutation_attempted = True  # includes partially successful setters that raise
                if start == cfg["disruption_start_inclusive"]:
                    connection.lane.setDisallowed(cfg["restricted_lane"], sorted(set(before[cfg["restricted_lane"]]["disallowed"]) | {cfg["passenger_class"]}))
                    event = "ACTIVATION"
                else:
                    connection.lane.setAllowed(cfg["restricted_lane"], baseline[cfg["restricted_lane"]]["allowed"])
                    connection.lane.setDisallowed(cfg["restricted_lane"], baseline[cfg["restricted_lane"]]["disallowed"])
                    event = "RESTORATION"
                after = _permissions(view, lanes)
                record["lifecycle"].append(dict(event=event, time=start, before=before, after=after))
                if event == "ACTIVATION" and _allowed(after[cfg["restricted_lane"]], cfg["passenger_class"]):
                    raise ValueError("RESTRICTION_DID_NOT_APPLY")
                if event == "RESTORATION":
                    if after != baseline:
                        raise ValueError("RESTORATION_MISMATCH")
                    restored = True
            stage = "OBSERVATION"
            observer.before_step(view, start)
            connection.simulationStep()
            end = view.simulation.getTime()
            active = sorted(view.vehicle.getIDList())
            if len(active) != len(set(active)) or set(active)-ids:
                raise ValueError("ACTIVE_IDENTITIES")
            monitor_states = _monitor_states(view, active, observer, cfg["monitored_edge"])
            observer.after_step(view, start, end)
            obs["step_intervals"].append([start, end])
            obs["final_time_seconds"] = end
            for method, key in (("getDepartedIDList", "departed_events"), ("getArrivedIDList", "arrival_events"),
                                ("getStartingTeleportIDList", "teleport_start_events"), ("getEndingTeleportIDList", "teleport_end_events")):
                for vehicle_id in getattr(view.simulation, method)():
                    obs[key].setdefault(vehicle_id, []).append(end)
            halted = []
            for vehicle_id in active:
                if view.vehicle.getVehicleClass(vehicle_id) != cfg["passenger_class"]:
                    raise ValueError("VEHICLE_CLASS_CHANGED")
                if tuple(view.vehicle.getRoute(vehicle_id)) != route_for[vehicle_id]:
                    raise ValueError("ROUTE_CHANGED")
                speed = _number(view.vehicle.getSpeed(vehicle_id))
                if speed < 0:
                    raise ValueError("NEGATIVE_SPEED")
                if speed < 0.1:
                    halted.append(vehicle_id); obs["per_trip_halting_seconds"][vehicle_id] += 1
            obs["queue_trace"].append([end, len(halted)])
            stage = "CONTROL_COLLECTION"
            controls = collector.controls(view)
            if controls != expected:
                raise ValueError("SCIENTIFIC_CONTROLS_CHANGED")
            diagnostic = collector.diagnostics(view)
            if set(diagnostic) != {"collisions", "invalid_routes", "simulator_errors"} or any(type(v) is not int or v < 0 for v in diagnostic.values()):
                raise ValueError("DIAGNOSTIC_SCHEMA")
            record["controls"]["steps"].append(dict(time=end, active_ids=active, halting_ids=halted,
                monitor_states=monitor_states, permissions=_permissions(view, lanes),
                controls_sha256=controls_sha, diagnostics=copy.deepcopy(diagnostic)))
        stage = "CUTOFF"
        obs["cutoff_active_ids"] = sorted(view.vehicle.getIDList())
        obs["cutoff_pending_ids"] = sorted(view.simulation.getPendingVehicles())
        record["controls"]["final"] = copy.deepcopy(collector.controls(view))
        record["controls"]["permissions_final"] = _permissions(view, lanes)
        observer.finalize(cfg["h_pilot_seconds"])
        record["summary"] = observer.summary_payload([r["vehicle_id"] for r in rows if cfg["monitored_edge"] in routes[r["route_id"]]])
        record["preactivation"] = observer.pre_activation_payload()
        obs["observations_complete"] = True
    except Exception as error:
        record["failure"] = {"kind": "TECHNICAL" if isinstance(error, OSError) else "INTEGRITY", "stage": stage, "code": type(error).__name__}
    finally:
        if observer is not None:
            record["events"] = copy.deepcopy(observer.events_payload())
        if mutation_attempted and not restored and baseline is not None:
            for method, key in (("setAllowed", "allowed"), ("setDisallowed", "disallowed")):
                try:
                    getattr(connection.lane, method)(cfg["restricted_lane"], baseline[cfg["restricted_lane"]][key])
                except Exception as error:
                    record["cleanup_failures"].append({"stage": "RESTORE_"+key.upper(), "code": type(error).__name__})
            try:
                if _permissions(view, lanes) != baseline:
                    raise ValueError("CLEANUP_PERMISSION_MISMATCH")
            except Exception as error:
                record["cleanup_failures"].append({"stage": "RESTORE_READBACK", "code": type(error).__name__})
        try:
            connection.close(wait=True)
        except Exception as error:
            record["cleanup_failures"].append({"stage": "CONNECTION_CLOSE", "code": type(error).__name__})
    try:
        raw = collector.finalize_output()
        obs["tripinfo_records"] = adapter.parse_tripinfo_xml(raw)
        record["output_finalized"] = True
    except Exception as error:
        if record["failure"] is None:
            record["failure"] = {"kind": "EVIDENCE", "stage": "TRIPINFO_FINALIZATION", "code": type(error).__name__}
    record["measurement"] = _account(record)
    return record


def _account(record):
    inputs = {k: v for k, v in record["observations"].items() if k != "step_intervals"}
    return adapter.account_trips(scheduled(record["binding"]), **inputs)


def validate_run(record):
    """Recompute accounting and validate evidence, not a supplied VALID label."""
    if not isinstance(record, dict) or set(record) != RUN_KEYS or type(record["schema_version"]) is not int or record["schema_version"] != 1 or record["integration_identity"] != IDENTITY or record["evidence_kind"] != "SYNTHETIC" or record["ready_to_run"] is not False:
        raise ValueError("RUN_SCHEMA")
    if not isinstance(record["run_id"], str) or not record["run_id"] or record["condition_label"] not in ("N0", "D0", "N0-CAL-R", "D0-CAL-R"):
        raise ValueError("RUN_IDENTITY")
    def error_record(value, keys):
        return (type(value) is dict and set(value) == set(keys)
                and all(type(value[k]) is str and value[k] for k in keys))
    if (record["failure"] is not None and
            (not error_record(record["failure"], ("kind","stage","code"))
             or record["failure"]["kind"] not in ("INTEGRITY","TECHNICAL","EVIDENCE"))):
        raise ValueError("FAILURE_SCHEMA")
    if (type(record["cleanup_failures"]) is not list
            or any(not error_record(v,("stage","code")) for v in record["cleanup_failures"])
            or type(record["output_finalized"]) is not bool
            or type(record["lifecycle"]) is not list
            or type(record["measurement"]) is not dict
            or any(v is not None and type(v) is not dict for v in
                   (record["events"],record["summary"],record["preactivation"]))):
        raise ValueError("RUN_STATUS_OR_EVIDENCE_SCHEMA")
    observations_keys = {"tripinfo_records","departed_events","arrival_events","cutoff_active_ids",
        "cutoff_pending_ids","per_trip_halting_seconds","queue_trace","teleport_start_events",
        "teleport_end_events","observations_complete","final_time_seconds","step_intervals"}
    if (type(record["observations"]) is not dict or set(record["observations"]) != observations_keys
            or type(record["observations"]["observations_complete"]) is not bool
            or type(record["controls"]) is not dict
            or set(record["controls"]) != {"initial","steps","final","permissions_initial","permissions_final"}
            or type(record["controls"]["steps"]) is not list):
        raise ValueError("OBSERVATION_CONTAINER_SCHEMA")
    checked_binding(record["binding"])
    measured = _account(record)
    errors = measured["integrity_errors"]; deficient = measured["evidence_deficiencies"]
    # Equality checks primitive evidence without attempting to sanitize raw NaN/Inf.
    if record["measurement"] != measured:
        errors.append("SUPPLIED_MEASUREMENT_DIFFERS_FROM_RECOMPUTATION")
    cfg = record["binding"]["scientific_configuration"]; h = cfg["h_pilot_seconds"]
    obs = record["observations"]; controls = record["controls"]
    if obs["step_intervals"] != [[t, t+1] for t in range(h)]:
        errors.append("CALLBACK_COVERAGE")
    if record["failure"]:
        (deficient if record["failure"]["kind"] == "EVIDENCE" else errors).append("FIRST_FAILURE:"+record["failure"]["stage"])
    if record["cleanup_failures"]:
        deficient.append("CLEANUP_FAILURE")
    if record["output_finalized"] is not True:
        deficient.append("OUTPUT_NOT_FINALIZED")
    try:
        expected = expected_controls(record["binding"])
        expected_sha = digest(expected)
        if controls["initial"] != expected or controls["final"] != expected:
            raise ValueError("SCIENTIFIC_CONTROLS")
        baseline = controls["permissions_initial"]
        restricted, surviving = cfg["restricted_lane"], cfg["surviving_lane"]
        if set(baseline) != {restricted, surviving} or controls["permissions_final"] != baseline or not all(_allowed(p,cfg["passenger_class"]) for p in baseline.values()):
            raise ValueError("PERMISSION_BASELINE_OR_FINAL")
        if len(controls["steps"]) != h:
            raise ValueError("CONTROL_COVERAGE")
        halted_counts = {key: 0 for key in measured["ledger"]}
        for time, sample in enumerate(controls["steps"], 1):
            if sample["time"] != time or sample["controls_sha256"] != expected_sha:
                raise ValueError("CONTROL_TIME_OR_BINDING")
            active = sample["active_ids"]; halted = sample["halting_ids"]
            expected_active = {v for v, times in obs["departed_events"].items() if len(times)==1 and times[0] <= time and (v not in obs["arrival_events"] or time < obs["arrival_events"][v][0])}
            if len(active) != len(set(active)) or set(active) != expected_active or len(halted) != len(set(halted)) or not set(halted) <= set(active) or obs["queue_trace"][time-1] != [time,len(halted)]:
                raise ValueError("ACTIVE_OR_HALTING_EVIDENCE")
            for v in halted:
                halted_counts[v] += 1
            permissions = copy.deepcopy(baseline)
            if record["condition_label"].startswith("D0") and cfg["disruption_start_inclusive"] < time <= cfg["disruption_end_exclusive"]:
                permissions[restricted]["disallowed"] = sorted(set(permissions[restricted]["disallowed"]) | {cfg["passenger_class"]})
            if sample["permissions"] != permissions:
                raise ValueError("UNEXPECTED_PERMISSION_TRANSITION")
            if set(sample["diagnostics"]) != {"collisions","invalid_routes","simulator_errors"} or any(type(v) is not int or v != 0 for v in sample["diagnostics"].values()):
                raise ValueError("COLLISION_ROUTE_OR_SIMULATOR_ERROR")
        if halted_counts != obs["per_trip_halting_seconds"] or controls["steps"][-1]["active_ids"] != obs["cutoff_active_ids"]:
            raise ValueError("CUTOFF_OR_HALTING_MISMATCH")
        _replay_exposure(record)
        summary, events, pre = record["summary"], record["events"], record["preactivation"]
        if summary["observer_identity"] != adapter.OBSERVER_IDENTITY or summary["run_id"] != record["run_id"] or summary["exposure_observability_complete"] is not True or summary["cutoff_seconds"] != h or pre["simulation_time_seconds"] != cfg["disruption_start_inclusive"] or events["run_id"] != record["run_id"]:
            raise ValueError("EXPOSURE_COVERAGE_OR_IDENTITY")
        transitions = [e for e in events["events"] if e["event"] in ("RESTRICTION_ACTIVATION", "RESTORATION", "PERMISSION_CHANGE")]
        is_d0 = record["condition_label"].startswith("D0")
        start, end = cfg["disruption_start_inclusive"], cfg["disruption_end_exclusive"]
        expected_transitions = [("RESTRICTION_ACTIVATION",start,restricted),("RESTORATION",end,restricted)] if is_d0 else []
        if [(e["event"],e["observed_at_seconds"],e["lane_id"]) for e in transitions] != expected_transitions:
            raise ValueError("EVENT_LIFECYCLE")
        if [(e["event"], e["time"]) for e in record["lifecycle"]] != ([("ACTIVATION",start),("RESTORATION",end)] if is_d0 else []):
            raise ValueError("OPERATION_LIFECYCLE")
        for operation, event in zip(record["lifecycle"],transitions):
            if operation["before"][restricted] != event["before_permissions"] or operation["after"][restricted] != event["after_permissions"]:
                raise ValueError("OPERATION_OBSERVER_MISMATCH")
        for period in ("before", "during", "after"):
            visits = {key for key,row in summary["per_vehicle"].items() if any(v["entry_period"]==period.upper() for v in row["edge_visits"])}
            if sorted(visits) != summary["unique_edge_entries"][period] or len(visits) != summary["unique_edge_entry_counts"][period] or not visits <= set(measured["ledger"]):
                raise ValueError("EXPOSURE_VISITS_OR_COUNTS")
        compliance = summary["lane_visit_diagnostics"][restricted]
        entries = [v for row in summary["per_vehicle"].values() for v in row["lane_visits"] if v["lane_id"]==restricted and v["entry_period"]=="DURING"]
        if compliance["post_activation_entry_count"] != len(entries) or (is_d0 and entries):
            raise ValueError("RESTRICTED_LANE_VISIT_COMPLIANCE")
        if any(v is None or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in measured["metrics"].values()):
            deficient.append("REQUIRED_METRIC_UNAVAILABLE")
    except (KeyError, TypeError, ValueError, IndexError, OverflowError, AssertionError) as error:
        errors.append("OBSERVATION_OR_CONTROL_EVIDENCE:"+str(error))
    measured["integrity_errors"] = sorted(set(errors)); measured["evidence_deficiencies"] = sorted(set(deficient))
    measured["measurement_status"] = "INTEGRITY_FAILURE" if errors else "EVIDENCE_DEFICIENCY" if deficient else "VALID"
    return measured


def normalized_scientific(record):
    m = validate_run(record)
    if m["measurement_status"] != "VALID":
        raise ValueError("INVALID_REPEAT_MEASUREMENT")
    normalized = {
        "per_vehicle_trip_accounting": m["ledger"],
        "per_vehicle_restricted_trip_times": {k:v["restricted_trip_time_seconds"] for k,v in m["ledger"].items()},
        "restricted_mean_and_p95_trip_time": {k:v for k,v in m["metrics"].items() if k.startswith("restricted_")},
        "complete_queue_trace": record["observations"]["queue_trace"],
        "normalized_exposure_events_and_summary": {"events":record["events"],"summary":record["summary"]},
        "preactivation_occupancy": record["preactivation"], "event_lifecycle": record["lifecycle"],
        "lane_visit_compliance": record["summary"]["lane_visit_diagnostics"],
        "route_file_sha256": record["binding"]["route_file_sha256"],
    }
    excluded = set(contract()["selected_deterministic_repeat"]["operational_fields_excluded"])
    def without_operational(value):
        if isinstance(value, dict):
            return {key: without_operational(item) for key, item in value.items() if key not in excluded}
        if isinstance(value, list):
            return [without_operational(item) for item in value]
        return value
    return without_operational(normalized)
