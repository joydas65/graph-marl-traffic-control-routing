"""Actual worker/collector/writer checks with synthetic factories only.

The concrete Popen call is inspected through an in-memory replacement. No test
creates a process, imports a native client, or opens a socket.
"""

import copy
from dataclasses import replace
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.b0.od_integration_v1 import evidence as io, finalization as final
from scripts.b0.od_integration_v1 import native_worker as worker
from test_b0_od_integration_live_binding import BOUNDS, Fixture


class Clock:
    def __init__(self):
        self.now = 10.0
    def __call__(self):
        return self.now


class NativeWorkerTests(unittest.TestCase):
    def fixture(self, **kwargs):
        fixture = Fixture(**kwargs)
        self.addCleanup(fixture.close)
        return fixture

    def execute(self, fixture, events, **kwargs):
        options = dict(process_factory=fixture.process_factory,
                       transport_factory=fixture.transport_factory,
                       owned_scope_verified=True)
        options.update(kwargs)
        return worker.execute_worker(fixture.plan, BOUNDS, events.append, **options)

    def readback(self, done):
        context = final.ReferenceContext(final.ReferenceGrant(**grant) for grant in done['grants'])
        return io.readback(done['receipt'], references=context)

    def test_actual_worker_positive_strict_handoff_is_not_calibration_success(self):
        fixture = self.fixture(condition='D0')
        events = []
        done = self.execute(fixture, events)
        self.assertEqual(set(done), {'receipt','grants','child_reaped','assessment','first_failure',
                                    'cleanup_handoff'})
        self.assertIsNone(done['cleanup_handoff'])  # No native GO context in this legacy double.
        self.assertEqual(done['assessment']['measurement_status'], 'VALID')
        self.assertIsNone(done['assessment']['stop_status'])
        self.assertIsNone(done['first_failure'])
        self.assertTrue(done['child_reaped'])
        self.assertEqual([event['phase'] for event in events if event['type'] == 'PHASE'],
                         ['CONNECT','RUN','FINALIZE'])
        payload = self.readback(done)
        self.assertEqual(worker.validate_worker_result(fixture.plan, done), payload)
        self.assertEqual(payload['record_kind'], 'RUN')
        self.assertEqual(payload['record']['schema_version'], 2)
        self.assertEqual(payload['evidence_kind'], 'SYNTHETIC')
        self.assertIs(payload['ready_to_run'], False)
        self.assertEqual(payload['record']['finalization']['collection_state'], 'COMPLETED')
        self.assertEqual(len(done['grants']), 1)
        self.assertLess(len(json.dumps(done).encode()), 16384)
        self.assertEqual(len([call for call in fixture.calls if call[0] == 'start']), 1)

    def test_actual_worker_late_error_and_missing_tripinfo_persist_failure(self):
        fixture = self.fixture(stderr=b'Error: Synthetic late worker finding.\n', missing=True)
        events = []
        done = self.execute(fixture, events)
        self.assertEqual(done['assessment']['stop_status'], 'FAIL')
        self.assertIn('UNEXPLAINED_SIMULATOR_ERROR', done['assessment']['reason_codes'])
        payload = self.readback(done)
        self.assertEqual(payload['record_kind'], 'FAILURE')
        self.assertEqual(payload['record']['experiment_status'], 'FAIL')
        self.assertEqual(payload['record']['run']['finalization']['tripinfo']['availability'], 'MISSING')
        firsts = [event['failure'] for event in events if event['type'] == 'FIRST_FAILURE']
        self.assertEqual(firsts, [payload['record']['run']['failure']])
        self.assertEqual(done['first_failure'], firsts[0])
        self.assertEqual(done['receipt']['persistence_status'], 'VERIFIED')

    def test_persistence_io_failure_cannot_replace_known_integrity_fail(self):
        fixture = self.fixture(stderr=b'Error: Synthetic integrity finding.\n', missing=True)
        events = []
        create = io._create
        def fail_result(directory, name, raw):
            if name == worker.RESULT_NAME:
                raise OSError('synthetic result write interruption')
            return create(directory, name, raw)
        with patch.object(io, '_create', side_effect=fail_result):
            with self.assertRaises(io.EvidenceError) as caught:
                self.execute(fixture, events)
        self.assertEqual(caught.exception.experiment_status, 'FAIL')
        failure = caught.exception.worker_failure
        self.assertEqual(failure['assessment']['stop_status'], 'FAIL')
        self.assertEqual(failure['first_failure']['code'], 'UNEXPLAINED_SIMULATOR_ERROR')
        self.assertTrue(failure['child_reaped'])
        self.assertIsNone(failure['receipt'])
        self.assertTrue((fixture.output / (worker.RESULT_NAME + '.pending')).exists())
        self.assertFalse((fixture.output / (worker.RESULT_NAME + '.complete.json')).exists())

    def test_factory_exception_has_operational_receipt_not_fabricated_run(self):
        fixture = self.fixture()
        calls, events = [], []
        def failed(plan, *, timeout):
            calls.append(timeout)
            raise OSError('synthetic acquisition unavailable')
        with self.assertRaises(OSError) as caught:
            self.execute(fixture, events, process_factory=failed)
        failure = caught.exception.worker_failure
        self.assertFalse(failure['child_reaped'])
        self.assertIsNone(failure['assessment'])
        self.assertIsNone(failure['receipt'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(failure['first_failure']['operation'], 'PROCESS_START')
        self.assertFalse((fixture.output / worker.RESULT_NAME).exists())
        self.assertFalse(any(event.get('phase') == 'RUN' for event in events))

    def test_owned_scope_and_origin_gate_precede_any_factory(self):
        fixture = self.fixture()
        cases = [dict(owned_scope_verified=False), dict(transport_factory=None)]
        for options in cases:
            with self.subTest(options=tuple(options)):
                with self.assertRaises(ValueError):
                    self.execute(fixture, [], **options)
        with self.assertRaisesRegex(ValueError, 'FACTORY_ORIGIN'):
            worker.execute_worker(fixture.plan, BOUNDS, lambda event: None,
                                  owned_scope_verified=True)
        with self.assertRaisesRegex(ValueError, 'FACTORY_ORIGIN'):
            worker.execute_worker(replace(fixture.plan, evidence_kind='LIVE'), BOUNDS,
                                  lambda event: None, owned_scope_verified=True,
                                  process_factory=fixture.process_factory,
                                  transport_factory=fixture.transport_factory)
        self.assertEqual(fixture.calls, [])

    def test_expired_supervisor_start_deadline_prevents_late_spawn(self):
        fixture = self.fixture()
        clock = Clock()
        with self.assertRaises(TimeoutError):
            self.execute(fixture, [], clock=clock, startup_deadline=clock.now,
                         total_deadline=clock.now + 100)
        self.assertEqual(fixture.calls, [])

    def test_late_child_handle_is_cleaned_before_connect_without_relaunch(self):
        fixture = self.fixture()
        clock, calls, events = Clock(), [], []
        class Child:
            pid = 4321
            def terminate(self, *, timeout):
                calls.append('terminate')
            def wait(self, *, timeout):
                calls.append('wait')
                return 0
            def kill(self, *, timeout):
                calls.append('kill')
        def late(plan, *, timeout):
            calls.append('start')
            clock.now += timeout + 1
            return Child()
        with self.assertRaises(TimeoutError) as caught:
            self.execute(fixture, events, process_factory=late, clock=clock)
        self.assertEqual(calls, ['start','terminate','wait'])
        self.assertTrue(caught.exception.worker_failure['child_reaped'])
        self.assertEqual(caught.exception.worker_failure['first_failure']['stage'], 'PROCESS_START')
        self.assertFalse(any(event.get('phase') == 'CONNECT' for event in events))
        self.assertFalse((fixture.output / worker.RESULT_NAME).exists())

    def test_late_connection_is_closed_and_never_used_as_running_connection(self):
        fixture = self.fixture()
        clock, events = Clock(), []
        def late(**kwargs):
            clock.now += kwargs['timeout'] + 1
            return fixture.backend
        with self.assertRaises(TimeoutError) as caught:
            self.execute(fixture, events, transport_factory=late, clock=clock)
        self.assertTrue(fixture.backend.closed)
        self.assertTrue(caught.exception.worker_failure['child_reaped'])
        self.assertEqual(caught.exception.worker_failure['first_failure']['stage'], 'TRANSPORT_CONNECT')
        self.assertFalse(any(event.get('phase') == 'RUN' for event in events))
        self.assertFalse(any(item[0] == 'advance' for item in fixture.backend.log))
        self.assertFalse((fixture.output / worker.RESULT_NAME).exists())

    def test_lost_failure_reporting_does_not_mask_original_or_prevent_cleanup(self):
        fixture = self.fixture()
        clock, calls = Clock(), []
        class Child:
            def terminate(self, *, timeout): calls.append('terminate')
            def wait(self, *, timeout): calls.append('wait'); return 0
            def kill(self, *, timeout): calls.append('kill')
        def late(plan, *, timeout):
            clock.now += timeout + 1
            return Child()
        def emit(event):
            if event['type'] == 'FIRST_FAILURE':
                raise BrokenPipeError('synthetic lost IPC')
        with self.assertRaises(TimeoutError) as caught:
            worker.execute_worker(fixture.plan, BOUNDS, emit, process_factory=late,
                                  transport_factory=fixture.transport_factory, clock=clock,
                                  owned_scope_verified=True)
        self.assertEqual(calls, ['terminate','wait'])
        self.assertEqual(caught.exception.worker_failure['reporting_errors'], ['BrokenPipeError'])
        self.assertTrue(caught.exception.worker_failure['child_reaped'])

    def test_lost_finalize_reporting_does_not_skip_late_child_cleanup(self):
        fixture = self.fixture()
        clock, calls = Clock(), []
        class Child:
            def terminate(self, *, timeout): calls.append('terminate')
            def wait(self, *, timeout): calls.append('wait'); return 0
            def kill(self, *, timeout): calls.append('kill')
        def late(plan, *, timeout):
            clock.now += timeout + 1
            return Child()
        def emit(event):
            if event.get('phase') == 'FINALIZE':
                raise BrokenPipeError('synthetic lost finalization notice')
        with self.assertRaises(TimeoutError) as caught:
            worker.execute_worker(fixture.plan, BOUNDS, emit, process_factory=late,
                                  transport_factory=fixture.transport_factory, clock=clock,
                                  owned_scope_verified=True)
        failure = caught.exception.worker_failure
        self.assertEqual(calls, ['terminate','wait'])
        self.assertEqual(failure['reporting_errors'], ['BrokenPipeError'])
        self.assertEqual(failure['first_failure']['code'], 'TimeoutError')
        self.assertTrue(failure['child_reaped'])

    def test_failed_finalize_notice_does_not_prevent_actual_close_or_wait(self):
        calls = []
        def failed(): raise BrokenPipeError('synthetic notice failure')
        class Target:
            def close(self, *, timeout): calls.append('close')
            def wait(self, *, timeout): calls.append('wait'); return 0
        process = worker._ObservedProcess(Target(), failed)
        transport = worker._FinalizingTransport(Target(), failed)
        with self.assertRaises(BrokenPipeError):
            transport.close(timeout=1)
        with self.assertRaises(BrokenPipeError):
            process.wait(timeout=1)
        self.assertEqual(calls, ['close','wait'])
        self.assertTrue(process.reaped)

    def test_concrete_popen_call_is_inherited_group_and_uses_actual_output_descriptors(self):
        fixture = self.fixture()
        (fixture.output / 'original-stderr.log').unlink()
        clock, captured = Clock(), {}
        child = SimpleNamespace(pid=9876)
        def fake_popen(argv, **kwargs):
            captured['argv'] = argv
            captured['kwargs'] = kwargs.copy()
            os.write(kwargs['stdout'], b'SYNTHETIC STDOUT\n')
            os.write(kwargs['stderr'], b'SYNTHETIC STDERR\n')
            return child
        with patch('subprocess.Popen', side_effect=fake_popen):
            process = worker._spawn_native(fixture.plan, deadline=clock.now + 3, clock=clock)
        self.assertEqual(captured['argv'], fixture.plan.argv)
        self.assertEqual(set(captured['kwargs']), {'stdin','stdout','stderr','close_fds'})
        self.assertTrue(captured['kwargs']['close_fds'])
        self.assertIs(process.process, child)
        self.assertEqual((fixture.output / 'original-stdout.log').read_bytes(), b'SYNTHETIC STDOUT\n')
        self.assertEqual((fixture.output / 'original-stderr.log').read_bytes(), b'SYNTHETIC STDERR\n')
        for name in ('stdout','stderr'):
            with self.assertRaises(OSError):
                os.fstat(captured['kwargs'][name])

    def test_concrete_factory_rechecks_deadline_after_file_acquisition_before_popen(self):
        fixture = self.fixture()
        (fixture.output / 'original-stderr.log').unlink()
        clock = Clock()
        opener = os.open
        def delayed(path, *args, **kwargs):
            descriptor = opener(path, *args, **kwargs)
            if path == 'original-stderr.log':
                clock.now += 4
            return descriptor
        with patch.object(os, 'open', side_effect=delayed), patch('subprocess.Popen') as popen:
            with self.assertRaises(TimeoutError):
                worker._spawn_native(fixture.plan, deadline=clock.now + 3, clock=clock)
        popen.assert_not_called()

    def test_spawn_failure_keeps_original_and_attempts_both_descriptor_closes(self):
        fixture = self.fixture()
        (fixture.output / 'original-stderr.log').unlink()
        clock, descriptors, closed = Clock(), [], []
        closer = os.close
        original = OSError('synthetic original spawn failure')
        def failed_popen(argv, **kwargs):
            descriptors.extend([kwargs['stdout'], kwargs['stderr']])
            raise original
        def close(descriptor):
            closer(descriptor)
            if descriptor in descriptors:
                closed.append(descriptor)
                if descriptor == descriptors[0]:
                    raise RuntimeError('synthetic first descriptor close failure')
        with patch('subprocess.Popen', side_effect=failed_popen), patch.object(os, 'close', side_effect=close):
            with self.assertRaises(OSError) as caught:
                worker._spawn_native(fixture.plan, deadline=clock.now + 3, clock=clock)
        self.assertIs(caught.exception, original)
        self.assertEqual(closed, descriptors)
        self.assertEqual(caught.exception.native_cleanup,
                         [dict(operation='CLOSE_LOG_DESCRIPTOR', exception='RuntimeError')])
        self.assertFalse(hasattr(caught.exception, 'unreturned_process'))

    def test_post_spawn_descriptor_failure_retains_child_for_owned_cleanup(self):
        fixture = self.fixture()
        (fixture.output / 'original-stderr.log').unlink()
        clock, descriptors, calls, closed = Clock(), [], [], []
        closer = os.close
        class Child:
            pid = 1234
            def terminate(self): calls.append('terminate')
            def wait(self, *, timeout): calls.append('wait'); return 0
            def kill(self): calls.append('kill')
        def popen(argv, **kwargs):
            calls.append('start')
            descriptors.extend([kwargs['stdout'], kwargs['stderr']])
            return Child()
        def close(descriptor):
            closer(descriptor)
            if descriptor in descriptors:
                closed.append(descriptor)
                if descriptor == descriptors[0]:
                    raise OSError('synthetic post-acquisition descriptor failure')
        def factory(plan, *, timeout):
            return worker._spawn_native(plan, deadline=clock.now + timeout, clock=clock)
        with patch('subprocess.Popen', side_effect=popen), patch.object(os, 'close', side_effect=close):
            with self.assertRaises(OSError) as caught:
                self.execute(fixture, [], process_factory=factory, clock=clock)
        self.assertEqual(closed, descriptors)
        self.assertEqual(calls, ['start','terminate','wait'])
        failure = caught.exception.worker_failure
        self.assertTrue(failure['child_reaped'])
        self.assertEqual(failure['native_cleanup'],
                         [dict(operation='CLOSE_LOG_DESCRIPTOR', exception='OSError')])
        self.assertIsNone(failure['assessment'])
        self.assertIsNone(failure['receipt'])

    def test_concrete_wait_retains_reaping_if_late_return_is_rejected(self):
        clock, calls = Clock(), []
        def late_wait(*, timeout):
            calls.append(timeout)
            clock.now += timeout + 1
            return 0
        child = SimpleNamespace(pid=1234, wait=late_wait)
        process = worker._NativeProcess(child, clock)
        with self.assertRaises(TimeoutError):
            process.wait(timeout=2)
        self.assertEqual(calls, [2])
        self.assertEqual(process.exit_code, 0)

    def test_parent_readback_rejects_swapped_explicit_grant_or_receipt(self):
        fixture = self.fixture()
        done = self.execute(fixture, [])
        for target in ('grant_origin', 'grant_run', 'receipt_directory', 'receipt_name',
                       'grant_count', 'grant_extra'):
            with self.subTest(target=target):
                changed = copy.deepcopy(done)
                if target == 'grant_origin':
                    changed['grants'][0]['evidence_kind'] = 'LIVE'
                elif target == 'grant_run':
                    changed['grants'][0]['run_id'] = 'unrelated-synthetic-run'
                elif target == 'receipt_directory':
                    changed['receipt']['output_directory'] = 'unrelated-synthetic-directory'
                elif target == 'receipt_name':
                    changed['receipt']['name'] = 'unrelated.json'
                elif target == 'grant_count':
                    changed['grants'] = []
                else:
                    changed['grants'][0]['unapproved'] = True
                with self.assertRaises(ValueError):
                    worker.validate_worker_result(fixture.plan, changed)


if __name__ == '__main__':
    unittest.main()
