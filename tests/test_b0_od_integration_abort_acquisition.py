"""Genuine acquisition/checkpoint regressions; all native operations injected."""

import os
from dataclasses import replace
import unittest
from unittest.mock import patch

from scripts.b0.od_integration_v1 import native_worker as worker
from test_b0_od_integration_live_binding import BOUNDS, Fixture
from test_b0_od_integration_native_worker import Clock


class RawChild:
    """Popen-shaped signatures: terminate/kill do not accept adapter timeouts."""
    pid = 9876

    def __init__(self, calls, *, cleanup_errors=False):
        self.calls, self.cleanup_errors = calls, cleanup_errors
        self.wait_count = 0

    def terminate(self):
        self.calls.append('terminate')
        if self.cleanup_errors:
            raise PermissionError('synthetic exact-child termination failure')

    def wait(self, *, timeout):
        self.calls.append(('wait', timeout))
        self.wait_count += 1
        if self.cleanup_errors and self.wait_count == 1:
            raise TimeoutError('synthetic first wait timeout')
        return -9 if self.cleanup_errors else -15

    def kill(self):
        self.calls.append('kill')


class AbortAcquisitionTests(unittest.TestCase):
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

    def no_result(self, fixture, failure):
        self.assertIsNone(failure['assessment'])
        self.assertIsNone(failure['receipt'])
        self.assertFalse((fixture.output / worker.RESULT_NAME).exists())

    def concrete_factory(self, fixture, clock, shutdown_requested=None):
        (fixture.output / 'original-stderr.log').unlink()
        def factory(plan, *, timeout):
            return worker._spawn_native(plan, deadline=clock.now + timeout,
                                        clock=clock, shutdown_requested=shutdown_requested)
        return factory

    def test_shutdown_before_start_prevents_factory_and_scientific_publication(self):
        fixture, events = self.fixture(), []
        with self.assertRaisesRegex(InterruptedError, 'WORKER_SHUTDOWN_REQUESTED') as caught:
            self.execute(fixture, events, shutdown_requested=lambda: True)
        self.assertEqual(fixture.calls, [])
        self.assertFalse(caught.exception.worker_failure['child_reaped'])
        self.no_result(fixture, caught.exception.worker_failure)

    def test_concrete_factory_rechecks_shutdown_immediately_before_popen(self):
        fixture, clock, shutdown = self.fixture(), Clock(), [False]
        factory = self.concrete_factory(fixture, clock, lambda: shutdown[0])
        opener = os.open
        def open_log(name, *args, **kwargs):
            descriptor = opener(name, *args, **kwargs)
            if name == 'original-stderr.log':
                shutdown[0] = True
            return descriptor
        with patch.object(os, 'open', side_effect=open_log), patch('subprocess.Popen') as popen:
            with self.assertRaises(InterruptedError) as caught:
                self.execute(fixture, [], process_factory=factory, clock=clock,
                             shutdown_requested=lambda: shutdown[0])
        popen.assert_not_called()
        self.assertFalse(hasattr(caught.exception, 'unreturned_process'))
        self.no_result(fixture, caught.exception.worker_failure)

    def test_shutdown_during_popen_retains_actual_handle_before_adapter_and_cleans(self):
        fixture, clock, shutdown, calls = self.fixture(), Clock(), [False], []
        factory = self.concrete_factory(fixture, clock, lambda: shutdown[0])
        child = RawChild(calls)
        def popen(*args, **kwargs):
            calls.append('start')
            shutdown[0] = True
            return child
        with patch('subprocess.Popen', side_effect=popen), patch.object(worker, '_NativeProcess') as adapter:
            with self.assertRaises(InterruptedError) as caught:
                self.execute(fixture, [], process_factory=factory, clock=clock,
                             shutdown_requested=lambda: shutdown[0])
        adapter.assert_not_called()
        self.assertIs(caught.exception.unreturned_process.process, child)
        self.assertEqual(calls, ['start', 'terminate', ('wait', BOUNDS.terminate_wait)])
        self.assertTrue(caught.exception.worker_failure['child_reaped'])
        self.no_result(fixture, caught.exception.worker_failure)

    def test_adapter_failure_keeps_original_and_exact_raw_handle_cleanup_signatures(self):
        for cleanup_errors in (False, True):
            with self.subTest(cleanup_errors=cleanup_errors):
                fixture, clock, calls = self.fixture(), Clock(), []
                factory = self.concrete_factory(fixture, clock)
                child = RawChild(calls, cleanup_errors=cleanup_errors)
                original = RuntimeError('synthetic adapter construction failure')
                def popen(*args, **kwargs):
                    calls.append('start')
                    return child
                with patch('subprocess.Popen', side_effect=popen), patch.object(
                        worker, '_NativeProcess', side_effect=original) as adapter:
                    with self.assertRaises(RuntimeError) as caught:
                        self.execute(fixture, [], process_factory=factory, clock=clock)
                self.assertIs(caught.exception, original)
                self.assertEqual(adapter.call_count, 1)
                self.assertIs(original.unreturned_process.process, child)
                expected = ['start', 'terminate', ('wait', BOUNDS.terminate_wait)]
                if cleanup_errors:
                    expected += ['kill', ('wait', BOUNDS.kill_wait)]
                    self.assertEqual([item.get('exception') for item in original.worker_failure[
                        'unreturned_cleanup']], ['PermissionError', 'TimeoutError', None, None])
                self.assertEqual(calls, expected)
                self.assertTrue(original.worker_failure['child_reaped'])
                self.assertEqual(original.worker_failure['first_failure']['code'], 'RuntimeError')
                self.no_result(fixture, original.worker_failure)

    def test_adapter_error_precedes_descriptor_cleanup_error_and_keeps_handle(self):
        fixture, clock, calls, descriptors = self.fixture(), Clock(), [], []
        factory = self.concrete_factory(fixture, clock)
        child, original = RawChild(calls), RuntimeError('synthetic adapter failure')
        close = os.close
        def popen(*args, **kwargs):
            descriptors.extend([kwargs['stdout'], kwargs['stderr']])
            return child
        def close_log(descriptor):
            close(descriptor)
            if descriptors and descriptor == descriptors[0]:
                raise OSError('synthetic descriptor close failure')
        with patch('subprocess.Popen', side_effect=popen), patch.object(
                worker, '_NativeProcess', side_effect=original), patch.object(os, 'close', side_effect=close_log):
            with self.assertRaises(RuntimeError) as caught:
                self.execute(fixture, [], process_factory=factory, clock=clock)
        self.assertIs(caught.exception, original)
        self.assertEqual(calls, ['terminate', ('wait', BOUNDS.terminate_wait)])
        self.assertEqual(original.native_cleanup,
                         [dict(operation='CLOSE_LOG_DESCRIPTOR', exception='OSError')])

    def test_creation_error_does_not_fabricate_unreturned_child_or_replace_error(self):
        fixture, clock, shutdown = self.fixture(), Clock(), [False]
        factory = self.concrete_factory(fixture, clock, lambda: shutdown[0])
        original = OSError('synthetic creation did not return a handle')
        def popen(*args, **kwargs):
            shutdown[0] = True
            raise original
        with patch('subprocess.Popen', side_effect=popen) as spawn:
            with self.assertRaises(OSError) as caught:
                self.execute(fixture, [], process_factory=factory, clock=clock,
                             shutdown_requested=lambda: shutdown[0])
        self.assertIs(caught.exception, original)
        self.assertEqual(spawn.call_count, 1)
        self.assertFalse(hasattr(original, 'unreturned_process'))
        self.assertFalse(original.worker_failure['child_reaped'])
        self.no_result(fixture, original.worker_failure)

    def test_injected_returned_handle_shutdown_cleans_without_child_or_connect_message(self):
        fixture, clock, shutdown, calls, events = self.fixture(), Clock(), [False], [], []
        child = worker._NativeProcess(RawChild(calls), clock)
        def factory(plan, *, timeout):
            calls.append('start')
            shutdown[0] = True
            return child
        with self.assertRaises(InterruptedError) as caught:
            self.execute(fixture, events, process_factory=factory, clock=clock,
                         shutdown_requested=lambda: shutdown[0])
        self.assertEqual(calls, ['start', 'terminate', ('wait', BOUNDS.terminate_wait)])
        self.assertFalse(any(event['type'] == 'CHILD' or event.get('phase') == 'CONNECT' for event in events))
        self.assertTrue(caught.exception.worker_failure['child_reaped'])

    def test_shutdown_at_child_or_connect_notice_prevents_transport_factory(self):
        for trigger in ('CHILD', 'CONNECT'):
            with self.subTest(trigger=trigger):
                fixture, clock, shutdown, calls = self.fixture(), Clock(), [False], []
                child = worker._NativeProcess(RawChild(calls), clock)
                def emit(event):
                    if event.get('type') == trigger or event.get('phase') == trigger:
                        shutdown[0] = True
                with patch.object(fixture, 'transport_factory') as connect:
                    with self.assertRaises(InterruptedError) as caught:
                        worker.execute_worker(fixture.plan, BOUNDS, emit,
                            process_factory=lambda plan, timeout: child,
                            transport_factory=connect, clock=clock, owned_scope_verified=True,
                            shutdown_requested=lambda: shutdown[0])
                connect.assert_not_called()
                self.assertEqual(calls, [('wait', BOUNDS.wait)])
                self.assertTrue(caught.exception.worker_failure['child_reaped'])
                self.no_result(fixture, caught.exception.worker_failure)

    def test_shutdown_during_connection_retains_and_closes_before_any_run_exchange(self):
        fixture, shutdown, events = self.fixture(), [False], []
        def connect(**kwargs):
            shutdown[0] = True
            return fixture.backend
        with self.assertRaises(InterruptedError) as caught:
            self.execute(fixture, events, transport_factory=connect,
                         shutdown_requested=lambda: shutdown[0])
        self.assertTrue(fixture.backend.closed)
        self.assertTrue(caught.exception.worker_failure['child_reaped'])
        self.assertFalse(any(event.get('phase') == 'RUN' for event in events))
        self.assertFalse(any(event[0] == 'advance' for event in fixture.backend.log))
        self.assertEqual(caught.exception.worker_failure['first_failure']['stage'], 'TRANSPORT_CONNECT')
        self.no_result(fixture, caught.exception.worker_failure)

    def test_shutdown_during_run_notice_closes_connection_before_collection(self):
        fixture, shutdown = self.fixture(), [False]
        def emit(event):
            if event.get('phase') == 'RUN':
                shutdown[0] = True
        with self.assertRaises(InterruptedError) as caught:
            worker.execute_worker(fixture.plan, BOUNDS, emit,
                process_factory=fixture.process_factory, transport_factory=fixture.transport_factory,
                owned_scope_verified=True, shutdown_requested=lambda: shutdown[0])
        self.assertTrue(fixture.backend.closed)
        self.assertTrue(caught.exception.worker_failure['child_reaped'])
        self.assertFalse(any(event[0] == 'advance' for event in fixture.backend.log))
        self.no_result(fixture, caught.exception.worker_failure)

    def test_genuine_run_callback_rejects_abort_but_finalize_exchange_remains_available(self):
        # Exercise the concrete branch's callback with *both* native operations
        # replaced. No client loader, socket, process or LIVE result is produced.
        from scripts.b0.od_integration_v1 import native_transport
        fixture, clock, shutdown, callbacks, events = self.fixture(), Clock(), [False], [], []
        plan = replace(fixture.plan, evidence_kind='LIVE')
        close = fixture.backend.close
        def connect_native(process, plan, timeout, transport_timeout, **kwargs):
            callbacks.append(kwargs['on_exchange'])
            return fixture.backend
        def close_transport(*, timeout):
            callbacks[0]('BEGIN', clock.now + timeout)
            close(timeout=timeout)
            callbacks[0]('END', clock.now + timeout)
        original = InterruptedError('synthetic RUN shutdown boundary')
        def exercise(plan, *, process_factory, transport_factory, **kwargs):
            process = process_factory(plan, timeout=BOUNDS.startup)
            connection = transport_factory(process=process, plan=plan,
                timeout=BOUNDS.connect, transport_timeout=BOUNDS.transport)
            shutdown[0] = True
            with self.assertRaisesRegex(InterruptedError, 'WORKER_SHUTDOWN_REQUESTED'):
                callbacks[0]('BEGIN', clock.now + BOUNDS.transport)
            connection.close(timeout=BOUNDS.close)
            self.assertEqual(process.wait(timeout=BOUNDS.wait), 0)
            raise original
        with patch.object(worker, '_spawn_native', return_value=fixture.process) as spawn, patch.object(
                native_transport, 'connect_native', side_effect=connect_native), patch.object(
                worker.live, 'observe_owned', side_effect=exercise), patch.object(
                fixture.backend, 'close', side_effect=close_transport):
            with self.assertRaises(InterruptedError) as caught:
                worker.execute_worker(plan, BOUNDS, events.append, clock=clock,
                    owned_scope_verified=True, startup_deadline=clock.now + 10,
                    total_deadline=clock.now + 100, cleanup_token='a' * 32, worker_pid=4567,
                    shutdown_requested=lambda: shutdown[0])
        self.assertIs(caught.exception, original)
        self.assertEqual(spawn.call_count, 1)
        self.assertTrue(fixture.backend.closed)
        self.assertTrue(original.worker_failure['child_reaped'])
        self.assertEqual([event['type'] for event in events if event['type'].startswith('EXCHANGE_')],
                         ['EXCHANGE_BEGIN', 'EXCHANGE_END'])
        self.no_result(fixture, original.worker_failure)

    def test_shutdown_after_actual_collection_prevents_assessment_and_keeps_integrity_first(self):
        for integrity in (False, True):
            with self.subTest(integrity=integrity):
                fixture = self.fixture(stderr=b'Error: synthetic original integrity failure\n' if integrity else b'')
                shutdown, after_observe = [False], []
                observe, assess = worker.live.observe_owned, worker.core.assess_run
                def collect(*args, **kwargs):
                    result = observe(*args, **kwargs)
                    shutdown[0] = True
                    return result
                def assessment(*args, **kwargs):
                    if shutdown[0]:
                        after_observe.append('assessment')
                    return assess(*args, **kwargs)
                with patch.object(worker.live, 'observe_owned', side_effect=collect), patch.object(
                        worker.core, 'assess_run', side_effect=assessment):
                    with self.assertRaises(InterruptedError) as caught:
                        self.execute(fixture, [], shutdown_requested=lambda: shutdown[0])
                self.assertEqual(after_observe, [])
                self.assertTrue(fixture.backend.closed)
                self.assertTrue(caught.exception.worker_failure['child_reaped'])
                if integrity:
                    self.assertEqual(caught.exception.worker_failure['first_failure']['code'],
                                     'UNEXPLAINED_SIMULATOR_ERROR')
                self.no_result(fixture, caught.exception.worker_failure)

    def test_shutdown_after_assessment_prevents_result_write(self):
        fixture, shutdown, collected = self.fixture(), [False], [False]
        observe, assess = worker.live.observe_owned, worker.core.assess_run
        def collect(*args, **kwargs):
            result = observe(*args, **kwargs)
            collected[0] = True
            return result
        def assessment(*args, **kwargs):
            result = assess(*args, **kwargs)
            if collected[0]:
                shutdown[0] = True
            return result
        with patch.object(worker.live, 'observe_owned', side_effect=collect), patch.object(
                worker.core, 'assess_run', side_effect=assessment):
            with self.assertRaises(InterruptedError) as caught:
                self.execute(fixture, [], shutdown_requested=lambda: shutdown[0])
        self.assertEqual(caught.exception.worker_failure['assessment']['measurement_status'], 'VALID')
        self.assertIsNone(caught.exception.worker_failure['receipt'])
        self.assertFalse((fixture.output / worker.RESULT_NAME).exists())

    def test_shutdown_after_result_write_prevents_additional_readback_and_done(self):
        fixture, shutdown, after_write_reads = self.fixture(), [False], []
        write, read = worker.io.write_once, worker.io.readback
        def write_once(directory, name, *args, **kwargs):
            result = write(directory, name, *args, **kwargs)
            if name == worker.RESULT_NAME:
                shutdown[0] = True
            return result
        def readback(*args, **kwargs):
            if shutdown[0]:
                after_write_reads.append('readback')
            return read(*args, **kwargs)
        with patch.object(worker.io, 'write_once', side_effect=write_once), patch.object(
                worker.io, 'readback', side_effect=readback):
            with self.assertRaises(InterruptedError) as caught:
                self.execute(fixture, [], shutdown_requested=lambda: shutdown[0])
        self.assertEqual(after_write_reads, [])
        self.assertIsNotNone(caught.exception.worker_failure['receipt'])
        self.assertTrue((fixture.output / worker.RESULT_NAME).exists())

    def test_shutdown_after_independent_readback_prevents_returned_handoff(self):
        fixture, shutdown, published = self.fixture(), [False], [False]
        write, read = worker.io.write_once, worker.io.readback
        def write_once(directory, name, *args, **kwargs):
            result = write(directory, name, *args, **kwargs)
            if name == worker.RESULT_NAME:
                published[0] = True
            return result
        def readback(receipt, *args, **kwargs):
            result = read(receipt, *args, **kwargs)
            if published[0] and receipt['name'] == worker.RESULT_NAME:
                shutdown[0] = True
            return result
        with patch.object(worker.io, 'write_once', side_effect=write_once), patch.object(
                worker.io, 'readback', side_effect=readback):
            with self.assertRaises(InterruptedError) as caught:
                self.execute(fixture, [], shutdown_requested=lambda: shutdown[0])
        self.assertTrue(caught.exception.worker_failure['child_reaped'])
        self.assertIsNotNone(caught.exception.worker_failure['receipt'])


if __name__ == '__main__':
    unittest.main()
