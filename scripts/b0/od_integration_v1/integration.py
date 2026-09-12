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
            "output_finalized", "measurement", "operational_abort"}
LEGACY_REVISION = "c0be5ca5c0116179f901bd00410c74e581799c87"
# Exact accepted tuple only; lookup is exclusively for read-only legacy auditing.
LEGACY_SOURCE_SHA256 = {
    "__init__.py": "ce9ebb3cb49eaf584ca9d7c8dbea62af1461add513c25d34bc2357f70bb7fd6c",
    "integration.py": "aee3028c1e2fd6d8972955bbd5375cff083a1787f5ab26409182d28338a5de37",
    "qualification.py": "955c13ee956a929bce167eb6d61ea335967944596c7539959f55353c2fd3aec3",
    "evidence.py": "11b2995f5f161be2dff062a5d2c119fe396a954f2582e242e37de7576e5cb517",
}


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


def checked_binding(binding, *, legacy_revision=None):
    if not isinstance(binding, dict):
        raise ValueError("RUN_INPUT_OR_SOURCE_BINDING_CHANGED")
    expected = build_binding(repository_root(), binding.get("seed"), binding.get("level"))
    if legacy_revision is not None:
        if legacy_revision != LEGACY_REVISION:
            raise ValueError("UNREVIEWED_LEGACY_REVISION")
        expected["implementation_sha256"] = dict(LEGACY_SOURCE_SHA256)
    if binding != expected:
        raise ValueError("RUN_INPUT_OR_SOURCE_BINDING_CHANGED")
    return contract()


def scheduled(binding, *, legacy_revision=None):
    frozen = checked_binding(binding, legacy_revision=legacy_revision)
    return [dict(vehicle_id=t.vehicle_id, scheduled_departure_seconds=t.scheduled_departure_seconds,
                 route_id=t.route_id) for t in od_input.build_seed_allocations(frozen, binding["seed"])[binding["level"]]]


def materialize_input(binding, output_dir, *, evidence_kind="SYNTHETIC"):
    from .evidence import write_input_once, readback
    frozen = checked_binding(binding)
    trips = od_input.build_seed_allocations(frozen, binding["seed"])[binding["level"]]
    raw = od_input.serialize_routes(frozen, binding["seed"], binding["level"], trips) + b"\n"
    def validator(data):
        result = od_input.validate_routes_xml(frozen, binding["seed"], binding["level"], data)
        if data != raw or result["xml_sha256"] != binding["route_file_sha256"]:
            raise ValueError("INPUT_READBACK_MISMATCH")
    receipt = write_input_once(output_dir, f"{binding['seed']}-{binding['level']}.rou.xml", raw, validator,
                               evidence_kind=evidence_kind)
    if readback(receipt, validator=validator) != raw:
        raise ValueError("INPUT_READBACK_MISMATCH")
    return receipt


def expected_controls(binding, *, legacy_revision=None):
    """Raw static TLS definitions from the exact reviewed network, not a second table."""
    checked_binding(binding, legacy_revision=legacy_revision)
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
                       "getStartingTeleportIDList", "getEndingTeleportIDList", "getPendingVehicles",
                       "getOption", "getCollidingVehiclesIDList"},
        "vehicle": {"getIDList", "getVehicleClass", "getRoadID", "getLaneID", "getSpeed",
                    "getLanePosition", "getRouteIndex", "getRoute", "isRouteValid"},
        "lane": {"getAllowed", "getDisallowed", "getLastStepVehicleIDs"},
        "trafficlight": {"getIDList", "getProgram", "getAllProgramLogics", "getRedYellowGreenState", "getParameter"},
    }
    class Domain:
        def __init__(self, target, allowed):
            self._target, self._allowed = target, allowed
        def __getattr__(self, name):
            if name not in self._allowed:
                raise ValueError("UNEXPECTED_CONNECTION_MEMBER")
            return getattr(self._target, name)
    def __init__(self, connection):
        self._connection = connection
        for name, methods in self._GETTERS.items():
            if hasattr(connection, name):
                setattr(self, name, self.Domain(getattr(connection, name), methods))

    def getVersion(self):
        return self._connection.getVersion()


def normalized_controls(binding, value, evidence_kind="SYNTHETIC", *, expected=None):
    if type(value) is dict and set(value) == {"normalized", "native"}:
        from .live_binding import normalize_control_payload
        if value['native'].get('origin') != evidence_kind:
            raise ValueError('CONTROL_ORIGIN_MISMATCH')
        return normalize_control_payload(binding, value, _expected=expected)
    if evidence_kind != "SYNTHETIC":
        raise ValueError('LIVE_NATIVE_CONTROLS_REQUIRED')
    return value


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


def _replay_exposure(record, *, prefix=False, legacy_revision=None):
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
    if prefix:
        # The failed advance followed before_step, but never after_step. Replay
        # that permission observation without inventing a cutoff/finalization.
        replay.sample = record["operational_abort"]["readback"]
        observer.before_step(replay, record["operational_abort"]["time_before"])
        if observer.events_payload() != record["events"]:
            raise ValueError("EXPOSURE_PREFIX_REPLAY_MISMATCH")
        return
    observer.finalize(cfg["h_pilot_seconds"])
    routes = {r["id"]: r["edges"].split() for r in cfg["route_definitions"]}
    structural = [r["vehicle_id"] for r in scheduled(binding, legacy_revision=legacy_revision)
                  if cfg["monitored_edge"] in routes[r["route_id"]]]
    if (observer.events_payload() != record["events"]
            or observer.summary_payload(structural) != record["summary"]
            or observer.pre_activation_payload() != record["preactivation"]):
        raise ValueError("EXPOSURE_REPLAY_MISMATCH")


def observe_run(binding, condition_label, run_id, connection, collector, *, references=None, evidence_kind="SYNTHETIC"):
    """Observe one supplied connection, always without retry or a launch operation.

    collector.controls(read_only_connection) returns expected_controls-shaped
    raw definitions/settings and identity of the inputs actually configured and
    read back by its backend. A live collector must derive that evidence from
    the actual loaded inputs, never echo this expected binding. Its live mapping
    remains a separate unvalidated task. collector.diagnostics returns counts.
    collector.finalize_output(result) incrementally fills FinalizationResultV1
    observations after attempted close. Integration owns collection_state/parsing;
    a normal return alone proves neither complete nor clean evidence. New records
    are always schema 2; an absent read context never triggers legacy fallback.
    """
    frozen = checked_binding(binding)
    if evidence_kind not in ("SYNTHETIC", "LIVE") or type(evidence_kind) is not str:
        raise ValueError("EVIDENCE_ORIGIN")
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
    record = dict(schema_version=2, integration_identity=IDENTITY, evidence_kind=evidence_kind,
                  ready_to_run=False, run_id=run_id, condition_label=condition_label,
                  binding=copy.deepcopy(binding), observations=obs, summary=None, events=None,
                  preactivation=None, lifecycle=[], controls={"initial": None, "steps": [], "final": None,
                  "permissions_initial": None, "permissions_final": None}, failure=None,
                  cleanup_failures=[], output_finalized=False, measurement=None,
                  operational_abort=None)
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
        if callable(getattr(collector, 'permissions', None)):
            record['controls']['native_permissions_initial'] = collector.permissions()
            record['controls']['native_permissions_final'] = None
        if not all(_allowed(p, cfg["passenger_class"]) for p in baseline.values()):
            raise ValueError("INITIAL_PERMISSION")
        record["controls"]["initial"] = copy.deepcopy(collector.controls(view))
        if normalized_controls(binding, record["controls"]["initial"], evidence_kind, expected=expected) != expected:
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
            try:
                connection.simulationStep()
            except OSError as error:
                # A label alone is insufficient. Retain one bounded readback
                # attempt before cleanup; never retry the advance. Unsupported
                # or failed readback remains explicit, not fabricated evidence.
                abort = dict(operation="SIMULATION_STEP", time_before=start,
                             exception_code=type(error).__name__, readback=None)
                record["operational_abort"] = abort
                try:
                    abort["readback"] = dict(time=view.simulation.getTime(),
                        delta=view.simulation.getDeltaT(),
                        active_ids=sorted(view.vehicle.getIDList()),
                        permissions=_permissions(view, lanes),
                        controls=copy.deepcopy(collector.controls(view)),
                        diagnostics=copy.deepcopy(collector.diagnostics(view)))
                except Exception:
                    pass
                raise
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
            if normalized_controls(binding, controls, evidence_kind, expected=expected) != expected:
                raise ValueError("SCIENTIFIC_CONTROLS_CHANGED")
            diagnostic = collector.diagnostics(view)
            native = type(controls) is dict and set(controls) == {"normalized", "native"}
            if set(diagnostic) != {"collisions", "invalid_routes", "simulator_errors"} or any(
                    not (native and v is None) and (type(v) is not int or v < 0) for v in diagnostic.values()):
                raise ValueError("DIAGNOSTIC_SCHEMA")
            record["controls"]["steps"].append(dict(time=end, active_ids=active, halting_ids=halted,
                monitor_states=monitor_states, permissions=_permissions(view, lanes),
                controls_sha256=controls_sha, diagnostics=copy.deepcopy(diagnostic)))
            if native:
                record['controls']['steps'][-1]['native_permissions'] = collector.permissions()
        stage = "CUTOFF"
        obs["cutoff_active_ids"] = sorted(view.vehicle.getIDList())
        obs["cutoff_pending_ids"] = sorted(view.simulation.getPendingVehicles())
        record["controls"]["final"] = copy.deepcopy(collector.controls(view))
        record["controls"]["permissions_final"] = _permissions(view, lanes)
        if 'native_permissions_initial' in record['controls']:
            record['controls']['native_permissions_final'] = collector.permissions()
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
            if record["failure"] is None:
                record["failure"] = {"kind": "EVIDENCE", "stage": "CONNECTION_CLOSE", "code": type(error).__name__}
    from . import finalization
    terminal = finalization.new_result()
    terminal["collection_state"] = "INTERRUPTED"
    interrupted = False
    try:
        returned = collector.finalize_output(terminal)
        if returned is not None:
            raise ValueError("FINALIZER_MUST_RETURN_NONE")
    except Exception as error:
        interrupted = True
    # Never trust collector writes to the two integration-owned fields.
    terminal["collection_state"] = "INTERRUPTED" if interrupted else "COMPLETED"
    if type(terminal.get("tripinfo")) is dict:
        terminal["tripinfo"]["parsing"] = "NOT_ATTEMPTED"
    record["finalization"] = copy.deepcopy(terminal)
    facts = finalization.validate(record, references=references, acquiring=True)
    if type(record["finalization"].get("tripinfo")) is dict:
        record["finalization"]["tripinfo"]["parsing"] = facts["parsing"]
    if facts["rows"] is not None:
        obs["tripinfo_records"] = facts["rows"]
    record["output_finalized"] = facts["output_finalized"]
    # A supported finding already recorded by the collector precedes a later
    # acquisition exception. A witness derived only after interruption does not
    # invent an earlier chronology. Prior observation/cleanup failures win here.
    if interrupted and record["failure"] is None:
        candidates = terminal.get("findings", [])
        prior = next((v["code"] for v in (candidates if type(candidates) is list else [])
                      if type(v) is dict and type(v.get("code")) is str
                      and v["code"] in facts["witnesses"]
                      and v["code"] in facts["errors"]), None)
        record["failure"] = dict(kind="INTEGRITY" if prior else "EVIDENCE",
                                 stage="TRIPINFO_FINALIZATION", code=prior or "FINALIZER_EXCEPTION")
    if type(record["finalization"].get("findings")) is list:
        existing = [v.get("code") for v in record["finalization"]["findings"] if type(v) is dict]
        for code, keys in facts["witnesses"].items():
            if code not in existing:
                record["finalization"]["findings"].append(dict(code=code, evidence_keys=keys))
    if record["failure"] is None and (facts["errors"] or facts["deficiencies"]):
        record["failure"] = dict(kind="INTEGRITY" if facts["errors"] else "EVIDENCE",
                                 stage="TRIPINFO_FINALIZATION",
                                 code=(facts["errors"] or facts["deficiencies"])[0])
    record["measurement"] = _account(record)
    return record


def _account(record, *, legacy_revision=None):
    inputs = {k: v for k, v in record["observations"].items() if k != "step_intervals"}
    return adapter.account_trips(scheduled(record["binding"], legacy_revision=legacy_revision), **inputs)


def _validate_run(record, *, prefix=False, references=None, legacy_revision=None):
    """Shared evidence checks; prefix mode never returns a valid measurement."""
    version = 1 if legacy_revision is not None else 2
    keys = RUN_KEYS if version == 1 else RUN_KEYS | {"finalization"}
    if not isinstance(record, dict) or set(record) != keys or type(record["schema_version"]) is not int or record["schema_version"] != version or record["integration_identity"] != IDENTITY or record["evidence_kind"] not in (("SYNTHETIC",) if version == 1 else ("SYNTHETIC", "LIVE")) or record["ready_to_run"] is not False:
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
    if record["operational_abort"] is not None and type(record["operational_abort"]) is not dict:
        raise ValueError("ABORT_SCHEMA")
    observations_keys = {"tripinfo_records","departed_events","arrival_events","cutoff_active_ids",
        "cutoff_pending_ids","per_trip_halting_seconds","queue_trace","teleport_start_events",
        "teleport_end_events","observations_complete","final_time_seconds","step_intervals"}
    if (type(record["observations"]) is not dict or set(record["observations"]) != observations_keys
            or type(record["observations"]["observations_complete"]) is not bool
            or type(record["controls"]) is not dict
            or set(record["controls"]) not in (
                {"initial","steps","final","permissions_initial","permissions_final"},
                {"initial","steps","final","permissions_initial","permissions_final","native_permissions_initial","native_permissions_final"})
            or type(record["controls"]["steps"]) is not list):
        raise ValueError("OBSERVATION_CONTAINER_SCHEMA")
    checked_binding(record["binding"], legacy_revision=legacy_revision)
    measured = _account(record, legacy_revision=legacy_revision)
    errors = measured["integrity_errors"]; deficient = measured["evidence_deficiencies"]
    # Equality checks primitive evidence without attempting to sanitize raw NaN/Inf.
    if record["measurement"] != measured:
        errors.append("SUPPLIED_MEASUREMENT_DIFFERS_FROM_RECOMPUTATION")
    if version == 2:
        from .finalization import validate
        terminal = validate(record, references=references)
        errors.extend(terminal["errors"]); deficient.extend(terminal["deficiencies"])
    cfg = record["binding"]["scientific_configuration"]; h = cfg["h_pilot_seconds"]
    obs = record["observations"]; controls = record["controls"]
    if prefix:
        abort = record["operational_abort"]
        if (type(abort) is not dict or set(abort) != {"operation", "time_before", "exception_code", "readback"}
                or abort["operation"] != "SIMULATION_STEP"
                or type(abort["time_before"]) is not int or not 0 <= abort["time_before"] < h
                or type(abort["exception_code"]) is not str or not abort["exception_code"]
                or record["failure"] != {"kind": "TECHNICAL", "stage": "OBSERVATION", "code": abort["exception_code"]}):
            raise ValueError("UNSUPPORTED_OPERATIONAL_ABORT")
        h = abort["time_before"]
        boundary = abort["readback"]
        if (type(boundary) is not dict or set(boundary) != {"time", "delta", "active_ids", "permissions", "controls", "diagnostics"}
                or type(boundary["time"]) not in (int, float) or boundary["time"] != h
                or type(boundary["delta"]) not in (int, float) or boundary["delta"] != cfg["simulation_step_seconds"]
                or obs["observations_complete"] is not False or obs["final_time_seconds"] != h
                or obs["cutoff_active_ids"] != [] or obs["cutoff_pending_ids"] != []
                or record["summary"] is not None or record["preactivation"] is not None
                or controls["final"] is not None or controls["permissions_final"] is not None):
            raise ValueError("ABORT_BOUNDARY_OR_FALSE_COMPLETION")
        # These full-H errors are consequences ONLY if all prefix/boundary
        # checks below pass. All other Adapter contradictions retain precedence.
        errors[:] = [e for e in errors if e not in {
            "INCOMPLETE_OBSERVATION_HORIZON", "INVALID_OR_TRUNCATED_QUEUE_TRACE",
            "UNEXPLAINED_DISAPPEARANCE"}]
    if obs["step_intervals"] != [[t, t+1] for t in range(h)]:
        errors.append("CALLBACK_COVERAGE")
    if record["failure"] and not prefix:
        if version == 2 and record["failure"]["stage"] == "TRIPINFO_FINALIZATION":
            # Keep chronology, but a stored terminal severity is not a witness.
            # Lost support is deficient; an otherwise clean contradictory label
            # is invalid record evidence, not a demonstrated simulator error.
            if not terminal["errors"] and not terminal["deficiencies"]:
                errors.append("UNSUPPORTED_TERMINAL_FIRST_FAILURE")
        else:
            (deficient if record["failure"]["kind"] == "EVIDENCE" else errors).append("FIRST_FAILURE:"+record["failure"]["stage"])
    if record["operational_abort"] is not None and not prefix and record["failure"] is None:
        errors.append("ABORT_WITHOUT_FAILURE")
    if record["cleanup_failures"]:
        deficient.append("CLEANUP_FAILURE")
    if record["output_finalized"] is not True:
        deficient.append("OUTPUT_NOT_FINALIZED")
    try:
        expected = expected_controls(record["binding"], legacy_revision=legacy_revision)
        expected_sha = digest(expected)
        native = type(controls['initial']) is dict and set(controls['initial']) == {'normalized','native'}
        if normalized_controls(record['binding'], controls["initial"], record['evidence_kind'], expected=expected) != expected or (not prefix and normalized_controls(record['binding'], controls["final"], record['evidence_kind'], expected=expected) != expected):
            raise ValueError("SCIENTIFIC_CONTROLS")
        if native:
            from .native_mapping import normalize_permissions
            for phase in ('initial',) if prefix else ('initial','final'):
                retained = controls['native_permissions_'+phase]
                canonical = controls['permissions_'+phase]
                if set(retained) != set(canonical) or any(normalize_permissions(**retained[lane]) != canonical[lane] for lane in canonical):
                    raise ValueError('NATIVE_PERMISSION_REPRESENTATION')
        elif 'native_permissions_initial' in controls:
            raise ValueError('UNEXPECTED_NATIVE_REPRESENTATION')
        baseline = controls["permissions_initial"]
        restricted, surviving = cfg["restricted_lane"], cfg["surviving_lane"]
        if set(baseline) != {restricted, surviving} or (not prefix and controls["permissions_final"] != baseline) or not all(_allowed(p,cfg["passenger_class"]) for p in baseline.values()):
            raise ValueError("PERMISSION_BASELINE_OR_FINAL")
        if len(controls["steps"]) != h or (prefix and len(obs["queue_trace"]) != h):
            raise ValueError("CONTROL_COVERAGE")
        if prefix:
            for key in ("departed_events", "arrival_events", "teleport_start_events", "teleport_end_events"):
                if any(len(times) != 1 or not 1 <= _number(times[0]) <= h for times in obs[key].values()):
                    raise ValueError("EVENT_OUTSIDE_OBSERVED_PREFIX")
            for row in obs["tripinfo_records"]:
                if any(_number(float(row.get(key, -1))) > h for key in ("depart", "arrival")):
                    raise ValueError("TRIPINFO_OUTSIDE_OBSERVED_PREFIX")
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
            if native:
                from .native_mapping import normalize_permissions
                raw_permissions = sample['native_permissions']
                if set(raw_permissions) != set(permissions) or any(
                        set(raw_permissions[lane]) != {'allowed','disallowed'} or
                        normalize_permissions(**raw_permissions[lane]) != permissions[lane] for lane in permissions):
                    raise ValueError('NATIVE_PERMISSION_REPRESENTATION')
            elif 'native_permissions' in sample:
                raise ValueError('UNEXPECTED_NATIVE_REPRESENTATION')
            if set(sample["diagnostics"]) != {"collisions","invalid_routes","simulator_errors"} or any(
                    not (native and v is None) and (type(v) is not int or v != 0) for v in sample["diagnostics"].values()):
                raise ValueError("COLLISION_ROUTE_OR_SIMULATOR_ERROR")
        if halted_counts != obs["per_trip_halting_seconds"] or (not prefix and controls["steps"][-1]["active_ids"] != obs["cutoff_active_ids"]):
            raise ValueError("CUTOFF_OR_HALTING_MISMATCH")
        _replay_exposure(record, prefix=prefix, legacy_revision=legacy_revision)
        if prefix:
            permissions = copy.deepcopy(baseline)
            if record["condition_label"].startswith("D0") and cfg["disruption_start_inclusive"] <= h < cfg["disruption_end_exclusive"]:
                permissions[restricted]["disallowed"] = sorted(set(permissions[restricted]["disallowed"]) | {cfg["passenger_class"]})
            if (normalized_controls(record['binding'], boundary["controls"], record['evidence_kind'], expected=expected) != expected or boundary["permissions"] != permissions
                    or boundary["active_ids"] != (controls["steps"][-1]["active_ids"] if h else [])
                    or boundary["diagnostics"] != {"collisions": 0, "invalid_routes": 0, "simulator_errors": 0}
                    or any(type(v) is not int for v in boundary["diagnostics"].values())):
                raise ValueError("ABORT_READBACK_CONTRADICTION")
            transitions = [e for e in record["events"]["events"] if e["event"] in ("RESTRICTION_ACTIVATION", "RESTORATION", "PERMISSION_CHANGE")]
            expected_operations = [("ACTIVATION", cfg["disruption_start_inclusive"]), ("RESTORATION", cfg["disruption_end_exclusive"])] if record["condition_label"].startswith("D0") else []
            expected_operations = [(e,t) for e,t in expected_operations if t <= h]
            if ([(e["event"], e["time"]) for e in record["lifecycle"]] != expected_operations
                    or [(e["event"], e["observed_at_seconds"], e["lane_id"]) for e in transitions] !=
                    [("RESTRICTION_ACTIVATION" if e == "ACTIVATION" else e, t, restricted) for e,t in expected_operations]):
                raise ValueError("ABORT_PREFIX_LIFECYCLE")
            for operation, event in zip(record["lifecycle"], transitions):
                if (operation["before"][restricted] != event["before_permissions"]
                        or operation["after"][restricted] != event["after_permissions"]
                        or operation["before"][surviving] != baseline[surviving]
                        or operation["after"][surviving] != baseline[surviving]):
                    raise ValueError("ABORT_OPERATION_OBSERVER_MISMATCH")
            if record["condition_label"].startswith("D0") and any(
                    e["event"] == "ENTER_LANE" and e["lane_id"] == restricted
                    and cfg["disruption_start_inclusive"] < e["observed_at_seconds"] <= cfg["disruption_end_exclusive"]
                    for e in record["events"]["events"]):
                raise ValueError("RESTRICTED_LANE_VISIT_COMPLIANCE")
            # Deliberately no full-H summary, scientific metrics, or gates.
            measured["integrity_errors"] = sorted(set(errors))
            measured["measurement_status"] = "INTEGRITY_FAILURE" if errors else "EVIDENCE_DEFICIENCY"
            return measured
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


def validate_run(record, *, references=None):
    """Full-horizon measurement validity, including unusable aborted records."""
    return _validate_run(record, references=references)


def assess_run(record, *, references=None):
    """Separate experiment stop from measurement validity; never trust a label.

    Only a recorded step OSError with unchanged-clock readback and a verified
    observed prefix is supported here. This is consistency evidence, not an
    authentication claim about externally supplied records or a live adapter.
    """
    return _assessment(record, references=references)


def _assessment(record, *, references=None, legacy_revision=None):
    measured = _validate_run(record, references=references, legacy_revision=legacy_revision)
    status = measured["measurement_status"]
    stop = "FAIL" if status == "INTEGRITY_FAILURE" else "INCONCLUSIVE" if status == "EVIDENCE_DEFICIENCY" else None
    if record["operational_abort"] is not None:
        try:
            prefix = _validate_run(record, prefix=True, references=references, legacy_revision=legacy_revision)
            stop = "FAIL" if prefix["integrity_errors"] else "BLOCKED"
            reasons = prefix["integrity_errors"] or ["VERIFIED_STEP_ABORT_PREFIX"]
        except (KeyError, TypeError, ValueError, IndexError, OverflowError, AssertionError, OSError):
            stop, reasons = "FAIL", ["UNSUPPORTED_OR_CONTRADICTORY_ABORT_EVIDENCE"]
    else:
        reasons = measured["integrity_errors"] or measured["evidence_deficiencies"]
    return {"measurement": measured, "stop_status": stop,
            "qualification_evaluated": False, "reason_codes": reasons}


def audit_legacy_run(record, *, revision):
    """Explicit read-only V1 audit; not eligible for any new selection/writer."""
    if revision != LEGACY_REVISION:
        raise ValueError("UNREVIEWED_LEGACY_REVISION")
    return {**_assessment(record, legacy_revision=revision),
            "audit_context": "LEGACY_FINALIZATION_UNVERIFIED", "accepted_revision": revision}


def normalized_scientific(record, *, references=None):
    m = validate_run(record, references=references)
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
