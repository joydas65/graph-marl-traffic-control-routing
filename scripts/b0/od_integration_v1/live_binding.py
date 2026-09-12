"""Thin SUMO 1.27.1 binding. Importing this module never starts native work.

Factories are explicit, injected dependencies. Offline callers supply doubles;
origin is evidence provenance, never authorization to execute a launch plan.
"""
import copy
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import stat
import xml.etree.ElementTree as ET

from . import integration as core, evidence as io, finalization as final

VERSION = '1.27.1'
PROTOCOL = 22
REPRESENTATION = 'SUMO_1_27_1_CONTROLS_V1'


def require(ok, code):
    if not ok:
        raise ValueError(code)


def origin(value):
    require(type(value) is str and value in ('SYNTHETIC', 'LIVE'), 'EVIDENCE_ORIGIN')
    return value


def number(value):
    require(not isinstance(value, bool) and isinstance(value, (str, int, float)), 'NATIVE_NUMBER')
    result = float(value)
    require(math.isfinite(result), 'NATIVE_NUMBER')
    return result


def boolean(value):
    require(type(value) is str and value in ('true', 'false'), 'NATIVE_BOOLEAN')
    return value == 'true'


def settings(binding):
    cfg = binding['scientific_configuration']
    return {
        'begin': str(cfg['start_seconds']), 'end': str(cfg['h_pilot_seconds']),
        'step-length': str(cfg['simulation_step_seconds']),
        'seed': str(cfg['simulator_seed']), 'random': 'false',
        'time-to-teleport': str(cfg['time_to_teleport']),
        'waiting-time-memory': str(cfg['waiting_time_memory']),
        'max-depart-delay': str(cfg['max_depart_delay']),
        'device.rerouting.probability': str(cfg['device_rerouting_probability']),
        'person-device.rerouting.probability': str(cfg['person_device_rerouting_probability']),
        'tripinfo-output.write-unfinished': 'true',
        # Do not introduce negative undeparted waiting sentinels. At H all
        # scheduled trips are due; native delayed-insertion IDs prove pending.
        'tripinfo-output.write-undeparted': 'false',
        'ignore-route-errors': 'false', 'no-warnings': 'false',
        'aggregate-warnings': '-1', 'verbose': 'false', 'language': 'en',
        'log.timestamps': 'false', 'log.processid': 'false',
        'no-step-log': 'true', 'duration-log.disable': 'true',
    }


@dataclass(frozen=True)
class LaunchPlan:
    binding: dict
    run_id: str
    condition: str
    evidence_kind: str
    executable: str
    client_directory: str
    output_directory: str
    port: int
    argv: tuple
    input_sha256: dict
    client_sha256: dict
    executable_sha256: str

    @property
    def output_path(self):
        return io.WORKSPACE / self.output_directory


def build_launch_plan(binding, *, run_id, condition, executable, client_directory,
                      output_directory, port, evidence_kind='SYNTHETIC', overrides=()):
    """Read-only exact plan; input is materialized separately by the accepted writer."""
    core.checked_binding(binding); origin(evidence_kind)
    require(not overrides, 'LAUNCH_OVERRIDES_NOT_ALLOWED')
    require(type(port) is int and 1024 <= port <= 65535, 'EXPLICIT_UNPRIVILEGED_PORT_REQUIRED')
    require(type(run_id) is str and bool(io.NAME.fullmatch(run_id)), 'RUN_IDENTITY')
    require(condition in ('N0', 'D0', 'N0-CAL-R', 'D0-CAL-R'), 'RUN_IDENTITY')
    final._directory(output_directory)
    output = io.WORKSPACE / output_directory
    with io._directory(output):
        pass
    executable, client = Path(executable), Path(client_directory)
    require(executable.is_absolute() and client.is_absolute(), 'ABSOLUTE_RUNTIME_PATH_REQUIRED')
    require(executable.is_file() and not executable.is_symlink(), 'RUNTIME_EXECUTABLE_OBJECT')
    client_names = ('constants.py', 'connection.py', '_simulation.py', '_trafficlight.py', '_lane.py', '_vehicle.py')
    client_hashes = {}
    for name in client_names:
        path = client / name
        require(path.is_file() and not path.is_symlink(), 'CLIENT_SOURCE_OBJECT')
        client_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    constants = (client / 'constants.py').read_text()
    import re
    require(re.search(r'^TRACI_VERSION\s*=\s*22\s*$', constants, re.M) is not None, 'CLIENT_PROTOCOL_MISMATCH')
    root = core.repository_root()
    network = root / 'configs/b0/b0-grid-3x3-v1/b0-grid-3x3.net.xml'
    config = root / 'configs/b0/b0-grid-3x3-v1/b0.sumocfg'
    route = output / f"{binding['seed']}-{binding['level']}.rou.xml"
    expected = core.expected_controls(binding)['input_identity']
    inputs = {'network': hashlib.sha256(network.read_bytes()).hexdigest(),
              'configuration': hashlib.sha256(config.read_bytes()).hexdigest()}
    with io._directory(output) as (fd, _):
        inputs['routes'] = hashlib.sha256(io._read(fd, route.name)).hexdigest()
    require(inputs == dict(network=expected['network_sha256'], configuration=expected['original_configuration_sha256'],
                           routes=expected['route_file_sha256']), 'LAUNCH_INPUT_MISMATCH')
    options = {'net-file': str(network), 'route-files': str(route), **settings(binding),
               'remote-port': str(port), 'tripinfo-output': str(output / 'original-tripinfo.xml'),
               'error-log': str(output / 'original-errors.log')}
    args = (str(executable), *(item for key, value in options.items() for item in ('--'+key, value)))
    return LaunchPlan(copy.deepcopy(binding), run_id, condition, evidence_kind, str(executable), str(client),
                      output_directory, port, args, inputs, client_hashes, hashlib.sha256(executable.read_bytes()).hexdigest())


def validate_plan(plan):
    require(type(plan) is LaunchPlan, 'LAUNCH_PLAN_TYPE')
    rebuilt = build_launch_plan(plan.binding, run_id=plan.run_id, condition=plan.condition,
        executable=plan.executable, client_directory=plan.client_directory,
        output_directory=plan.output_directory, port=plan.port, evidence_kind=plan.evidence_kind)
    require(rebuilt == plan, 'LAUNCH_PLAN_OR_RUNTIME_CHANGED')


def _logic(logic):
    return dict(programID=logic.programID, type=logic.type,
        phases=[dict(duration=p.duration, state=p.state, minDur=p.minDur, maxDur=p.maxDur,
                     next=list(p.next), name=p.name) for p in logic.phases])


def normalize_control_payload(binding, payload, *, _expected=None):
    """Re-derive canonical controls from retained query/input observations, not labels."""
    require(type(payload) is dict and set(payload) == {'normalized', 'native'}, 'NATIVE_CONTROLS_SCHEMA')
    raw = payload['native']
    require(set(raw) == {'representation', 'version', 'options', 'tls', 'input_sha256', 'origin', 'output_identity'}, 'NATIVE_CONTROLS_SCHEMA')
    require(raw['representation'] == REPRESENTATION, 'NATIVE_REPRESENTATION_VERSION')
    origin(raw['origin'])
    operational = raw['output_identity']
    require(set(operational) == {'loaded_paths','argument_paths'}, 'NATIVE_OPERATIONAL_BINDING')
    require(set(operational['loaded_paths']) == {'net-file','route-files','tripinfo-output','error-log','remote-port'}
            and operational['loaded_paths'] == operational['argument_paths'], 'RUNTIME_INPUT_OR_OUTPUT_PATH_MISMATCH')
    require(type(raw['version']) is list and len(raw['version']) == 2 and raw['version'][0] == PROTOCOL
            and type(raw['version'][0]) is int and raw['version'][1] == 'SUMO '+VERSION, 'RUNTIME_VERSION_MISMATCH')
    expected = core.expected_controls(binding) if _expected is None else _expected
    cfg = copy.deepcopy(binding['scientific_configuration'])
    queried = raw['options']; frozen = settings(binding)
    require(set(queried) == set(frozen), 'NATIVE_OPTION_COVERAGE')
    for key, wanted in frozen.items():
        got = queried[key]
        if wanted in ('true', 'false'):
            require(boolean(got) == boolean(wanted), 'RUNTIME_OPTION_MISMATCH')
        elif key == 'language':
            require(got == wanted, 'RUNTIME_OPTION_MISMATCH')
        else:
            require(number(got) == number(wanted), 'RUNTIME_OPTION_MISMATCH')
    for key, option in (('start_seconds','begin'), ('h_pilot_seconds','end'),
        ('simulation_step_seconds','step-length'), ('simulator_seed','seed'),
        ('time_to_teleport','time-to-teleport'), ('waiting_time_memory','waiting-time-memory'),
        ('max_depart_delay','max-depart-delay'), ('device_rerouting_probability','device.rerouting.probability'),
        ('person_device_rerouting_probability','person-device.rerouting.probability')):
        cfg[key] = number(queried[option])
    cfg['simulator_random_mode'] = boolean(queried['random'])
    cfg['dynamic_rerouting'] = (cfg['device_rerouting_probability'] != 0 or cfg['person_device_rerouting_probability'] != 0)
    input_identity = copy.deepcopy(expected['input_identity'])
    observed_inputs = raw['input_sha256']
    require(set(observed_inputs) == {'network','configuration','routes'}, 'INPUT_OBSERVATION_SCHEMA')
    for label, key in (('network','network_sha256'), ('configuration','original_configuration_sha256'), ('routes','route_file_sha256')):
        input_identity[key] = observed_inputs[label]
    # Seed/level/assignment labels are static declarations; byte hashes bind
    # them to exact writer-validated launch files. Never call them runtime queries.
    require(type(raw['tls']) is list and len(raw['tls']) == len(expected['tls']), 'TLS_COVERAGE')
    tls = []
    for item, wanted in zip(sorted(raw['tls'], key=lambda x:x['id']), expected['tls']):
        require(set(item) == {'id','program','offset','cycle','logics'}, 'TLS_OBSERVATION_SCHEMA')
        require(len(item['logics']) == 1, 'TLS_PROGRAM_COVERAGE')
        logic = item['logics'][0]
        require(set(logic) == {'programID','type','phases'} and type(logic['type']) is int and logic['type'] == 0,
                'TLS_NOT_STATIC')
        require(item['program'] == logic['programID'], 'TLS_ACTIVE_PROGRAM')
        require(number(item['offset']) == number(wanted['attributes']['offset']), 'TLS_OFFSET')
        require(number(item['cycle']) == sum(number(p['duration']) for p in wanted['phases']), 'TLS_CYCLE')
        phases = []
        for phase in logic['phases']:
            require(set(phase) == {'duration','state','minDur','maxDur','next','name'}, 'TLS_PHASE_SCHEMA')
            require(phase['next'] == [] and phase['name'] == '', 'TLS_EXTRA_PHASE_BEHAVIOR')
            require(number(phase['minDur']) == number(phase['duration']) and number(phase['maxDur']) == number(phase['duration']), 'TLS_DURATION_BOUNDS')
            phases.append(dict(duration=format(number(phase['duration']), '.15g'), state=phase['state']))
        tls.append(dict(attributes=dict(id=item['id'], type='static', programID=logic['programID'],
                                       offset=format(number(item['offset']), '.15g')), phases=phases))
    canonical = dict(scientific_configuration=cfg, input_identity=input_identity, tls=tls)
    require(payload['normalized'] == canonical, 'CONTROL_NORMALIZATION_MISMATCH')
    return canonical


class PermissionLane:
    """Permission-mask projection only; underlying raw getter pairs are retained."""
    def __init__(self, lane):
        self.target = lane
        self.raw = {}

    def _read(self, lane):
        from .native_mapping import normalize_permissions
        pair = dict(allowed=list(self.target.getAllowed(lane)), disallowed=list(self.target.getDisallowed(lane)))
        normalized = normalize_permissions(pair['allowed'], pair['disallowed'])
        self.raw[lane] = pair
        return normalized

    def getAllowed(self, lane):
        return self._read(lane)['allowed']

    def getDisallowed(self, lane):
        return self._read(lane)['disallowed']

    def __getattr__(self, name):
        if name not in ('setAllowed','setDisallowed','getLastStepVehicleIDs'):
            raise AttributeError(name)
        return getattr(self.target, name)


class BindingConnection:
    def __init__(self, runtime):
        self.runtime = runtime
        self.simulation = runtime.connection.simulation
        self.vehicle = runtime.connection.vehicle
        self.trafficlight = runtime.connection.trafficlight
        self.lane = PermissionLane(runtime.connection.lane)

    def getVersion(self):
        return self.runtime.connection.getVersion()

    def simulationStep(self):
        return self.runtime.simulationStep()

    def close(self, wait=True):
        return self.runtime.close(wait=wait)


def _read_original(directory, name):
    """Bounded anchored no-follow read; compare same descriptor before/after."""
    with io._directory(directory) as (fd, _):
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(descriptor)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= io.MAX_BYTES, 'OUTPUT_OBJECT')
            chunks, size = [], 0
            while True:
                chunk = os.read(descriptor, min(65536, io.MAX_BYTES+1-size))
                if not chunk:
                    break
                chunks.append(chunk); size += len(chunk)
                require(size <= io.MAX_BYTES, 'OUTPUT_SIZE_LIMIT')
            after = os.fstat(descriptor)
            require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) ==
                    (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns), 'OUTPUT_CHANGED_DURING_READ')
            raw = b''.join(chunks)
            return raw, dict(device=after.st_dev, inode=after.st_ino, byte_count=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        finally:
            os.close(descriptor)


class NativeCollector:
    def __init__(self, plan, runtime, connection, references):
        validate_plan(plan)
        require(type(references) is final.ReferenceContext, 'REFERENCE_CONTEXT_REQUIRED')
        self.plan, self.runtime, self.connection, self.references = plan, runtime, connection, references
        self.expected_controls = core.expected_controls(plan.binding)
        # Anchor the actual original output object BEFORE close/finalization.
        # No expected content digest is invented while the file may be growing.
        with io._directory(plan.output_path) as (fd, _):
            metadata = os.stat('original-tripinfo.xml', dir_fd=fd, follow_symlinks=False)
            require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1, 'OUTPUT_ANCHOR_OBJECT')
        self.expected = dict(device=metadata.st_dev, inode=metadata.st_ino, byte_count=None, sha256=None)
        references.authorize(final.ReferenceGrant(plan.run_id, plan.condition, core.digest(plan.binding), plan.output_directory, self.expected, plan.evidence_kind))
        self.native_permissions = []

    def controls(self, view):
        b = self.plan.binding
        # Recheck the actual files, executable/client identities and effective
        # runtime options; static allocation labels are identified separately.
        if view.simulation.getTime() in (0, b['scientific_configuration']['h_pilot_seconds']):
            validate_plan(self.plan)
        expected_paths = {'net-file':self.plan.argv[self.plan.argv.index('--net-file')+1],
                          'route-files':self.plan.argv[self.plan.argv.index('--route-files')+1],
                          'tripinfo-output':str(self.plan.output_path/'original-tripinfo.xml'),
                          'error-log':str(self.plan.output_path/'original-errors.log'),
                          'remote-port':str(self.plan.port)}
        loaded_paths = {key:view.simulation.getOption(key) for key in expected_paths}
        require(loaded_paths == expected_paths, 'RUNTIME_INPUT_OR_OUTPUT_PATH_MISMATCH')
        raw = dict(representation=REPRESENTATION, origin=self.plan.evidence_kind,
                   version=list(view.getVersion()), input_sha256=dict(self.plan.input_sha256),
                   options={key:view.simulation.getOption(key) for key in settings(b)}, tls=[],
                   output_identity=dict(loaded_paths=loaded_paths, argument_paths=expected_paths))
        for tls in sorted(view.trafficlight.getIDList()):
            raw['tls'].append(dict(id=tls, program=view.trafficlight.getProgram(tls),
                offset=view.trafficlight.getParameter(tls, 'offset'), cycle=view.trafficlight.getParameter(tls, 'cycleTime'),
                logics=[_logic(logic) for logic in view.trafficlight.getAllProgramLogics(tls)]))
        # Create candidate canonical representation from independently observed
        # queries, then cross-check it via the same readback normalization.
        cfg = copy.deepcopy(b['scientific_configuration'])
        identity = copy.deepcopy(self.expected_controls['input_identity'])
        for key,label in (('route_file_sha256','routes'),('network_sha256','network'),('original_configuration_sha256','configuration')):
            identity[key] = raw['input_sha256'][label]
        tls = [dict(attributes=dict(id=x['id'],type='static',programID=x['program'],offset=format(number(x['offset']),'.15g')),
               phases=[dict(duration=format(number(p['duration']),'.15g'),state=p['state']) for p in x['logics'][0]['phases']]) for x in raw['tls']]
        payload = dict(normalized=dict(scientific_configuration=cfg,input_identity=identity,tls=tls),native=raw)
        normalize_control_payload(b, payload, _expected=self.expected_controls)
        return payload

    def permissions(self):
        return copy.deepcopy(self.connection.lane.raw)

    def diagnostics(self, view):
        # No getter exposes an authoritative cumulative simulator-error count.
        # Missing coverage stays None; final logs independently provide coverage.
        try:
            collisions = view.simulation.getCollidingVehiclesIDList()
            require(type(collisions) in (list,tuple) and all(type(v) is str for v in collisions), 'COLLISION_GETTER_REPRESENTATION')
            collision_count = len(collisions)
        except (AttributeError, NotImplementedError):
            collision_count = None
        route_count, route_unknown = 0, False
        for vehicle in view.vehicle.getIDList():
            try:
                valid = view.vehicle.isRouteValid(vehicle)
                if type(valid) is not bool:
                    route_unknown = True
                elif not valid:
                    route_count += 1
            except (AttributeError, NotImplementedError):
                route_unknown = True
        return dict(collisions=collision_count, invalid_routes=route_count if route_count or not route_unknown else None, simulator_errors=None)

    def finalize_output(self, result):
        from .native_mapping import diagnostic_payload, parse_diagnostics
        result['process'] = copy.deepcopy(self.runtime.finalization_process)
        result['output_identity']['output_directory'] = self.plan.output_directory
        result['output_identity']['output_observations']['expected'] = copy.deepcopy(self.expected)
        artifacts = result['output_identity']['artifacts']
        failures = []
        def retain(key, raw, name):
            with io._directory(self.plan.output_path) as (fd, _):
                io._create(fd, name, raw)
                require(io._read(fd,name) == raw, 'RETAINED_BYTES_MISMATCH')
            artifacts[key] = dict(name=name,byte_count=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        def available(name):
            try:
                return _read_original(self.plan.output_path,name)[0]
            except OSError:
                return None
            except Exception as error:
                failures.append(error)
                return None
        exited = result['process']['state'] == 'EXITED'
        # Diagnostics first: accessible contradictions survive missing TripInfo.
        try:
            diagnostic = diagnostic_payload(available('original-errors.log'), stderr=available('original-stderr.log'),
                evidence_kind=self.plan.evidence_kind, finalized=exited)
            counts, coverage = parse_diagnostics(diagnostic, evidence_kind=self.plan.evidence_kind)
            retain('diagnostics', io._encode(diagnostic), 'retained-diagnostics.json')
        except Exception as error:
            failures.append(error)
        else:
            result['diagnostics'] = dict(counts=counts,coverage=coverage)
            for key,count in counts.items():
                if count:
                    result['findings'].append(dict(code=final.POSITIVE[key],evidence_keys=['diagnostics']))
        observed = None
        try:
            with io._directory(self.plan.output_path) as (fd, _):
                metadata = os.stat('original-tripinfo.xml', dir_fd=fd, follow_symlinks=False)
            observed = dict(device=metadata.st_dev,inode=metadata.st_ino,byte_count=None,sha256=None)
        except OSError:
            pass
        try:
            raw, observed = _read_original(self.plan.output_path, 'original-tripinfo.xml')
        except FileNotFoundError:
            result['tripinfo']['availability'] = 'MISSING'
            observed = None
        except OSError:
            result['tripinfo']['availability'] = 'UNREADABLE'
        except Exception as error:
            failures.append(error)
            result['tripinfo']['availability'] = 'UNREADABLE'
        else:
            try:
                retain('tripinfo', raw, 'retained-tripinfo.xml')
            except Exception as error:
                failures.append(error)
                result['tripinfo']['availability'] = 'UNREADABLE'
            else:
                result['tripinfo']['availability'] = 'AVAILABLE'
        if observed is not None:
            result['tripinfo']['identity'] = 'MATCH' if (observed['device'], observed['inode']) == (self.expected['device'],self.expected['inode']) else 'CONTRADICTED'
        result['output_identity']['output_observations']['observed'] = observed
        capture = dict(run_id=self.plan.run_id,condition_label=self.plan.condition,binding_sha256=core.digest(self.plan.binding),
                       process=result['process'],output_observations=result['output_identity']['output_observations'],
                       evidence_kind=self.plan.evidence_kind)
        try:
            retain('capture',io._encode(capture),'retained-capture.json')
        except Exception as error:
            failures.append(error)
        if failures:
            raise failures[0]


@dataclass(frozen=True)
class OwnedObservation:
    """Scientific record plus separate local ownership outcomes, not a new schema."""
    run: dict
    ownership: dict


def observe_owned(plan, *, bounds, process_factory, transport_factory, references):
    """One supplied plan, one owned process, no calibration loop or retry."""
    from .owned_runtime import OwnedRuntime
    validate_plan(plan)
    runtime = OwnedRuntime(plan, bounds=bounds, process_factory=process_factory, transport_factory=transport_factory)
    def ownership():
        return dict(run_id=plan.run_id,evidence_kind=plan.evidence_kind,
                    first_failure=runtime.first_failure,lifecycle=runtime.lifecycle)
    try:
        runtime.start()
        connection = BindingConnection(runtime)
        collector = NativeCollector(plan,runtime,connection,references)
        run = core.observe_run(plan.binding,plan.condition,plan.run_id,connection,collector,
                               references=references,evidence_kind=plan.evidence_kind)
    except BaseException as first:
        try:
            runtime.close()
        except BaseException:
            pass  # Earlier failure is retained; cleanup outcomes remain separate.
        first.ownership_evidence = ownership()
        raise
    return OwnedObservation(run,ownership())
