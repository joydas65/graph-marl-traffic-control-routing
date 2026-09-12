"""API-shaped synthetic tests of the actual thin binding; no native launch."""
import copy
from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.b0.od_integration_v1 import integration as core, evidence as io, finalization as final
from scripts.b0.od_integration_v1 import live_binding as live, native_mapping as mapping
from scripts.b0.od_integration_v1 import qualification as q
from scripts.b0.od_integration_v1.owned_runtime import RuntimeBounds, OwnedRuntime
from b0_od_integration_fixtures import FakeBackend, Lane

BOUNDS = RuntimeBounds(3,2,1,1,2,1,1)


class NativeLane(Lane):
    def getAllowed(self, lane):
        denied = set(self.b.permissions[lane]['disallowed'])
        return sorted(mapping.VEHICLE_CLASSES-denied) if denied else []

    def setAllowed(self, lane, values):
        self.b.permissions[lane]['disallowed'] = sorted(mapping.VEHICLE_CLASSES-set(values)) if values else []


class TLS:
    def __init__(self, binding):
        self.data = {v['attributes']['id']:v for v in core.expected_controls(binding)['tls']}
    def getIDList(self):
        return tuple(self.data)
    def getProgram(self, tls):
        return self.data[tls]['attributes']['programID']
    def getParameter(self, tls, key):
        return self.data[tls]['attributes']['offset'] if key == 'offset' else '68.00'
    def getAllProgramLogics(self, tls):
        item = self.data[tls]
        phases = [SimpleNamespace(duration=float(p['duration']),state=p['state'],minDur=float(p['duration']),
                  maxDur=float(p['duration']),next=(),name='') for p in item['phases']]
        return (SimpleNamespace(programID=item['attributes']['programID'],type=0,phases=tuple(phases)),)


class NativeDouble(FakeBackend):
    def __init__(self, plan, **kwargs):
        super().__init__(plan.binding,plan.condition,**kwargs)
        self.plan = plan
        self.lane = NativeLane(self)
        self.trafficlight = TLS(plan.binding)
        self.options = dict(zip((a[2:] for a in plan.argv[1::2]),plan.argv[2::2]))
        self.simulation.getOption = lambda key:self.options[key]
        self.simulation.getCollidingVehiclesIDList = lambda:[]
        # Unlike the old hand fixture, native pending excludes future demand.
        self.simulation.getPendingVehicles = lambda:sorted(v for v in self.pending if self.by_id[v]['scheduled_departure_seconds'] <= self.time)
        self.vehicle.isRouteValid = lambda vehicle:True
    def getVersion(self):
        return (22,'SUMO 1.27.1')
    def close(self, *, timeout):
        self.log.append(('bounded-close',timeout))
        super().close(wait=False)


class ProcessDouble:
    def __init__(self, backend, *, errors=b'', stderr=b'', missing=False, replace_object=False):
        self.backend,self.errors,self.stderr = backend,errors,stderr
        self.missing,self.replace_object = missing,replace_object
        self.waits = []
    def wait(self, *, timeout):
        self.waits.append(timeout)
        b = self.backend
        if not b.closed:
            raise AssertionError('wait before close')
        raw = b.tripinfo_bytes()
        # Explicit native-shaped premise: first actual insertion at time0 is
        # observed at callback1. Preserve bytes; adapter already uses [0,1].
        raw = raw.replace(b'depart="1"',b'depart="0"',1)
        original = b.plan.output_path/'original-tripinfo.xml'
        if self.missing:
            original.unlink()
        elif self.replace_object:
            replacement = b.plan.output_path/'replacement.xml'
            replacement.write_bytes(raw)
            replacement.replace(original)
        else:
            original.write_bytes(raw)
        (b.plan.output_path/'original-errors.log').write_bytes(self.errors)
        (b.plan.output_path/'original-stderr.log').write_bytes(self.stderr)
        return 0
    def terminate(self, *, timeout):
        raise AssertionError('unexpected terminate')
    def kill(self, *, timeout):
        raise AssertionError('unexpected kill')


class Fixture:
    def __init__(self, *, condition='N0', seed=20260904, references=None, **kwargs):
        parent = io.WORKSPACE/'synthetic-test-outputs'
        parent.mkdir(parents=True,exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='thin-native-double-',dir=parent)
        self.output = Path(self.temp.name)
        binary = self.output/'synthetic-sumo'
        binary.write_bytes(b'SYNTHETIC NONEXECUTABLE FIXTURE\n')
        client = self.output/'synthetic-client'; client.mkdir()
        for name in ('constants.py','connection.py','_simulation.py','_trafficlight.py','_lane.py','_vehicle.py'):
            (client/name).write_text('TRACI_VERSION = 22\n' if name == 'constants.py' else '# synthetic source identity only\n')
        self.binding = core.build_binding(core.repository_root(),seed,'C1')
        core.materialize_input(self.binding,self.output)
        self.plan = live.build_launch_plan(self.binding,run_id=f'synthetic-native-{seed}-{condition}',condition=condition,
            executable=binary,client_directory=client,output_directory=str(self.output.relative_to(io.WORKSPACE)),port=8873)
        for name in ('original-tripinfo.xml','original-errors.log','original-stderr.log'):
            (self.output/name).write_bytes(b'')
        backend_options = kwargs.pop('backend_options',{})
        self.backend = NativeDouble(self.plan,**backend_options)
        self.process = ProcessDouble(self.backend,**kwargs)
        self.refs = final.ReferenceContext(()) if references is None else references
        self.calls = []
    def process_factory(self, plan, *, timeout):
        self.calls.append(('start',timeout,plan.argv))
        return self.process
    def transport_factory(self, *, process, plan, timeout, transport_timeout):
        self.calls.append(('connect',timeout,transport_timeout))
        return self.backend
    def observe(self):
        return live.observe_owned(self.plan,bounds=BOUNDS,process_factory=self.process_factory,
                                  transport_factory=self.transport_factory,references=self.refs)
    def collector(self):
        runtime = OwnedRuntime(self.plan,bounds=BOUNDS,process_factory=self.process_factory,
                               transport_factory=self.transport_factory)
        runtime.start()
        connection = live.BindingConnection(runtime)
        collector = live.NativeCollector(self.plan,runtime,connection,self.refs)
        return runtime,connection,collector
    def close(self):
        self.temp.cleanup()


class NativeBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
    def test_exact_plan_and_overrides(self):
        f = self.fixture
        options = f.backend.options
        self.assertEqual(options['step-length'],'1')
        self.assertEqual(options['end'],'1500')
        self.assertEqual(options['tripinfo-output.write-unfinished'],'true')
        self.assertEqual(options['tripinfo-output.write-undeparted'],'false')
        self.assertEqual(options['seed'],'20260904')
        self.assertEqual({k:options[k] for k in mapping.REQUIRED_DIAGNOSTIC_OPTIONS},mapping.REQUIRED_DIAGNOSTIC_OPTIONS)
        self.assertFalse(any(x in f.plan.argv for x in ('--configuration-file','--load-state','--additional-files')))
        with self.assertRaisesRegex(ValueError,'PLAN_OR_RUNTIME_CHANGED'):
            live.validate_plan(replace(f.plan,argv=(*f.plan.argv,'--step-length','2')))
        with self.assertRaisesRegex(ValueError,'OVERRIDES'):
            live.build_launch_plan(f.binding,run_id='test',condition='N0',executable=f.plan.executable,
                client_directory=f.plan.client_directory,output_directory=f.plan.output_directory,port=8873,overrides={'seed':1})
    def test_input_client_and_runtime_mismatch(self):
        f = self.fixture
        (Path(f.plan.client_directory)/'connection.py').write_text('# changed synthetic source\n')
        with self.assertRaisesRegex(ValueError,'PLAN_OR_RUNTIME_CHANGED'):
            live.validate_plan(f.plan)
    def test_input_file_mismatch(self):
        f = self.fixture
        (f.output/'20260904-C1.rou.xml').write_bytes(b'<routes/>')
        with self.assertRaisesRegex(ValueError,'INPUT_MISMATCH'):
            live.validate_plan(f.plan)
    def test_actual_getters_normalized_and_retained(self):
        f = self.fixture; runtime,connection,collector = f.collector()
        controls = collector.controls(core.ReadOnlyConnection(connection))
        self.assertEqual(live.normalize_control_payload(f.binding,controls),core.expected_controls(f.binding))
        self.assertEqual(controls['native']['tls'][0]['logics'][0]['type'],0)
        self.assertEqual(controls['native']['options']['end'],'1500')
        self.assertIsNone(collector.diagnostics(core.ReadOnlyConnection(connection))['simulator_errors'])
        runtime.close()
    def test_runtime_path_mismatch_rejected(self):
        f = self.fixture; runtime,connection,collector = f.collector()
        f.backend.options['route-files'] = 'unrelated.rou.xml'
        with self.assertRaisesRegex(ValueError,'RUNTIME_INPUT'):
            collector.controls(core.ReadOnlyConnection(connection))
        runtime.close()
    def test_runtime_version_mismatch_rejected(self):
        f = self.fixture; runtime,connection,collector = f.collector()
        f.backend.getVersion = lambda:(22,'SUMO 1.26.0')
        with self.assertRaisesRegex(ValueError,'VERSION_MISMATCH'):
            collector.controls(core.ReadOnlyConnection(connection))
        runtime.close()
    def test_runtime_option_mismatch_rejected(self):
        f = self.fixture; runtime,connection,collector = f.collector()
        f.backend.options['random'] = 'true'
        with self.assertRaisesRegex(ValueError,'OPTION_MISMATCH'):
            collector.controls(core.ReadOnlyConnection(connection))
        runtime.close()
    def test_tls_offset_mismatch_rejected(self):
        f = self.fixture; runtime,connection,collector = f.collector()
        f.backend.trafficlight.getParameter = lambda tls,key:'1' if key == 'offset' else '68'
        with self.assertRaisesRegex(ValueError,'TLS_OFFSET'):
            collector.controls(core.ReadOnlyConnection(connection))
        runtime.close()
    def test_unsupported_diagnostic_getters_are_unavailable(self):
        f = self.fixture; runtime,connection,collector = f.collector()
        f.backend.simulation.getCollidingVehiclesIDList = lambda:(_ for _ in ()).throw(NotImplementedError())
        self.assertIsNone(collector.diagnostics(core.ReadOnlyConnection(connection))['collisions'])
        runtime.close()
    def test_native_pending_does_not_include_future_demand(self):
        self.assertEqual(self.fixture.backend.simulation.getPendingVehicles(),[])
        self.assertGreater(len(self.fixture.backend.departure),0)
    def test_facade_construction_failure_still_closes(self):
        f = self.fixture
        del f.backend.trafficlight
        with self.assertRaises(AttributeError) as caught:
            f.observe()
        self.assertTrue(f.backend.closed)
        self.assertIn('lifecycle',caught.exception.ownership_evidence)
    def test_grant_origin_substitution_rejected(self):
        f = self.fixture; runtime,connection,collector = f.collector()
        run = dict(run_id=f.plan.run_id,condition_label=f.plan.condition,binding=f.binding,evidence_kind='LIVE')
        with self.assertRaisesRegex(ValueError,'UNAUTHORIZED_REFERENCE_CONTEXT'):
            f.refs.grant(run,f.plan.output_directory)
        runtime.close()
    def test_native_mapping_origin_and_version_rejected(self):
        payload = mapping.diagnostic_payload(b'',stderr=b'',evidence_kind='SYNTHETIC',finalized=True)
        for key,value in (('version',2),('evidence_kind','LIVE')):
            with self.subTest(field=key):
                bad = copy.deepcopy(payload); bad[key] = value
                with self.assertRaises(ValueError):
                    mapping.parse_diagnostics(bad,evidence_kind='SYNTHETIC')


class NativeBindingEndToEndTests(unittest.TestCase):
    def make(self, **kwargs):
        fixture = Fixture(**kwargs)
        self.addCleanup(fixture.close)
        return fixture
    def test_actual_thin_positive_assessment_and_persistence(self):
        f = self.make(condition='D0')
        output = f.observe(); run = output.run
        assessment = core.assess_run(run,references=f.refs)
        self.assertEqual(assessment['measurement']['measurement_status'],'VALID',assessment)
        self.assertIsNone(assessment['stop_status'])
        self.assertEqual(run['evidence_kind'],'SYNTHETIC')
        self.assertEqual(run['observations']['tripinfo_records'][0]['depart'],'0')
        self.assertEqual(run['controls']['permissions_initial'],run['controls']['permissions_final'])
        self.assertIn('native_permissions_initial',run['controls'])
        self.assertTrue(output.ownership['lifecycle'])
        payload = {**io.PAYLOAD_BASE,'record_kind':'RUN','record':run}
        receipt = io.write_once(f.output,'positive.json',payload,references=f.refs)
        self.assertEqual(io.readback(receipt,references=f.refs),payload)
    def test_late_error_and_missing_tripinfo_retains_fail(self):
        f = self.make(errors=b'',stderr=b'Error: Synthetic terminal failure.\n',missing=True)
        run = f.observe().run
        assessment = core.assess_run(run,references=f.refs)
        self.assertEqual(assessment['stop_status'],'FAIL')
        self.assertIn('UNEXPLAINED_SIMULATOR_ERROR',assessment['measurement']['integrity_errors'])
        payload = {**io.PAYLOAD_BASE,'record_kind':'FAILURE','record':dict(failure_code='SYNTHETIC_LATE_ERROR',
            measurement_status=assessment['measurement']['measurement_status'],experiment_status='FAIL',run=run,raw_evidence=None)}
        receipt = io.write_once(f.output,'late.json',payload,references=f.refs)
        self.assertEqual(io.readback(receipt,references=f.refs),payload)
    def test_replaced_original_object_is_fail(self):
        f = self.make(replace_object=True)
        run = f.observe().run
        self.assertIn('OUTPUT_OBJECT_MISMATCH',core.assess_run(run,references=f.refs)['measurement']['integrity_errors'])
    def test_native_pending_and_active_population_preserved(self):
        f = self.make(backend_options={'active_count':2,'pending_count':2})
        run = f.observe().run
        self.assertEqual(len(run['observations']['cutoff_pending_ids']),2)
        self.assertEqual(len(run['observations']['cutoff_active_ids']),2)
        self.assertEqual(core.assess_run(run,references=f.refs)['measurement']['measurement_status'],'VALID')
    def test_unknown_warning_is_inconclusive_not_error(self):
        f = self.make(stderr=b'Warning: Unmapped synthetic warning.\n')
        run = f.observe().run
        self.assertEqual(core.assess_run(run,references=f.refs)['stop_status'],'INCONCLUSIVE')
        self.assertIsNone(run['finalization']['diagnostics']['counts']['simulator_errors'])
    def test_unsupported_native_step_loss_remains_fail(self):
        f = self.make(backend_options={'fail_step':3})
        run = f.observe().run
        self.assertEqual(run['failure']['kind'],'TECHNICAL')
        self.assertEqual(core.assess_run(run,references=f.refs)['stop_status'],'FAIL')
        self.assertIsNone(run['operational_abort']['readback']['diagnostics']['simulator_errors'])
    def test_earlier_log_read_failure_does_not_hide_stderr_error(self):
        f = self.make(stderr=b'Error: Synthetic terminal contradiction.\n')
        reader = live._read_original
        def fail_one(directory,name):
            if name == 'original-errors.log':
                raise ValueError('SYNTHETIC_ACQUISITION_FAILURE')
            return reader(directory,name)
        with patch.object(live,'_read_original',side_effect=fail_one):
            run = f.observe().run
        self.assertEqual(run['finalization']['collection_state'],'INTERRUPTED')
        self.assertIn('UNEXPLAINED_SIMULATOR_ERROR',core.assess_run(run,references=f.refs)['measurement']['integrity_errors'])
    def test_diagnostic_retention_failure_does_not_hide_output_replacement(self):
        f = self.make(replace_object=True)
        create = io._create
        def fail_one(fd,name,raw):
            if name == 'retained-diagnostics.json':
                raise OSError('synthetic retention failure')
            return create(fd,name,raw)
        with patch.object(io,'_create',side_effect=fail_one):
            run = f.observe().run
        self.assertEqual(run['finalization']['collection_state'],'INTERRUPTED')
        self.assertIn('OUTPUT_OBJECT_MISMATCH',core.assess_run(run,references=f.refs)['measurement']['integrity_errors'])
    def test_mapping_exception_does_not_hide_output_replacement(self):
        f = self.make(replace_object=True)
        with patch.object(mapping,'diagnostic_payload',side_effect=ValueError('SYNTHETIC_MAPPING_FAILURE')):
            run = f.observe().run
        self.assertEqual(run['finalization']['collection_state'],'INTERRUPTED')
        self.assertIn('OUTPUT_OBJECT_MISMATCH',core.assess_run(run,references=f.refs)['measurement']['integrity_errors'])
    def test_capture_retention_failure_cannot_hide_diagnostic_positive(self):
        f = self.make(stderr=b'Error: Synthetic terminal contradiction.\n')
        create = io._create
        def fail_capture(fd,name,raw):
            if name == 'retained-capture.json':
                raise OSError('synthetic capture retention failure')
            return create(fd,name,raw)
        with patch.object(io,'_create',side_effect=fail_capture):
            run = f.observe().run
        assessment = core.assess_run(run,references=f.refs)
        self.assertEqual(assessment['stop_status'],'FAIL')
        self.assertIn('UNEXPLAINED_SIMULATOR_ERROR',assessment['measurement']['integrity_errors'])
    def test_actual_native_shaped_selected_repeat_uses_frozen_exclusions(self):
        refs = final.ReferenceContext(())
        pairs = []
        for seed in core.contract()['calibration_seeds']:
            pairs.append(tuple(self.make(seed=seed,condition=condition,references=refs).observe().run for condition in ('N0','D0')))
        session = q.SelectionSession(references=refs)
        self.assertEqual(session.add_level('C1',pairs)['status'],'PROVISIONAL')
        repeated = tuple(self.make(condition=condition,references=refs).observe().run for condition in ('N0-CAL-R','D0-CAL-R'))
        self.assertEqual(session.add_repeats(*repeated)['status'],'PENDING_READBACK')
    def test_unreadable_replacement_retains_anchored_object_contradiction(self):
        f = self.make()
        wait = f.process.wait
        def replaced(*,timeout):
            result = wait(timeout=timeout)
            original = f.output/'original-tripinfo.xml'
            target = f.output/'synthetic-target.xml'; target.write_bytes(b'<tripinfos/>')
            original.unlink(); original.symlink_to(target)
            return result
        f.process.wait = replaced
        run = f.observe().run
        self.assertEqual(run['finalization']['tripinfo']['availability'],'UNREADABLE')
        self.assertIn('OUTPUT_OBJECT_MISMATCH',core.assess_run(run,references=f.refs)['measurement']['integrity_errors'])


if __name__ == '__main__':
    unittest.main()
