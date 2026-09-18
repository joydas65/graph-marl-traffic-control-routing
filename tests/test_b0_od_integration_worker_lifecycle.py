"""Genuine worker entry with explicit in-memory signal/control/process doubles.

Run through run_b0_od_integration_offline.py. No real signal installation,
scope observation, process, socket, client or sleep is used here.
"""
from dataclasses import asdict
import importlib.util
import json
import signal
import unittest
from unittest.mock import Mock, patch

from scripts.b0.od_integration_v1 import native_supervisor as supervisor
from scripts.b0.od_integration_v1 import native_worker as worker
import test_b0_od_integration_live_binding as fixtures
import test_b0_od_integration_terminal_cleanup as terminal_fixtures


class ScriptExhausted(BaseException):
    """Cannot be mistaken for a production control-pipe exception."""


class Control:
    """Finite scripted IO. Exhaustion fails, so a spinning loop cannot pass."""
    def __init__(self, reads=(), write_action=None, setup_error=None):
        self.reads = list(reads)
        self.write_action = write_action
        self.setup_error = setup_error
        self.events = []
        self.raw = b''
        self.handler = None
        self.now = 0.0

    def clock(self):
        return self.now

    def install_term(self, handler):
        self.events.append('install')
        self.handler = handler

    def setup(self):
        self.events.append('setup')
        if self.setup_error:
            raise self.setup_error
        return terminal_fixtures.WORKER_PID

    def term(self):
        self.handler(signal.SIGTERM, None)  # Python callback only, never a signal

    def read(self):
        self.events.append('read')
        self.now += .01
        if not self.reads:
            raise ScriptExhausted('scripted control input exhausted')
        value = self.reads.pop(0)
        if callable(value):
            value = value()
        if isinstance(value, BaseException):
            raise value
        return value

    def write(self, raw):
        self.events.append('write')
        count = self.write_action(raw) if self.write_action else len(raw)
        if count is not None:
            self.raw += raw[:count]
        return count

    def messages(self):
        return [json.loads(line) for line in self.raw.splitlines()]


class LifecycleTests(unittest.TestCase):
    def fixture(self):
        f = fixtures.Fixture()
        self.addCleanup(f.close)
        return f

    def go(self, f):
        bounds = supervisor.SupervisorBounds(fixtures.BOUNDS, 2, 20, 3, 4)
        return (json.dumps(dict(type='GO', plan=asdict(f.plan), bounds=asdict(bounds),
            startup_deadline=3, total_deadline=20,
            cleanup_token=terminal_fixtures.TOKEN))+'\n').encode()

    def run_main(self, control, execute=None, lifecycle=None):
        life = supervisor._WorkerLifecycle() if lifecycle is None else lifecycle
        call = Mock(return_value={}) if execute is None else execute
        code = supervisor.worker_main(ops=control, lifecycle=life, execute=call)
        return code, life, call

    def test_fresh_module_import_is_inert_under_native_denials(self):
        spec = importlib.util.spec_from_file_location(
            'scripts.b0.od_integration_v1._lifecycle_import_probe', supervisor.__file__)
        module = importlib.util.module_from_spec(spec)
        with patch.object(signal, 'signal', side_effect=AssertionError('signal install on import')) as install:
            spec.loader.exec_module(module)
        install.assert_not_called()
        self.assertTrue(callable(module.worker_main))

    def test_handler_only_latches_first_phase_and_is_sticky(self):
        life = supervisor._WorkerLifecycle()
        life.on_term(signal.SIGTERM, None)
        self.assertEqual(life.state, 'PRE_COMPLETION')
        self.assertEqual(life.term_state, 'PRE_COMPLETION')
        life.on_term(signal.SIGTERM, None)
        self.assertTrue(life.shutdown_requested())
        self.assertEqual(life.state, 'ABORT_RESERVED')
        with self.assertRaises(InterruptedError):
            life.arm_completed()
        self.assertEqual(life.state, 'ABORT_RESERVED')

    def test_ordinary_failure_reservation_cannot_arm_without_term(self):
        life = supervisor._WorkerLifecycle()
        life.reserve()
        with self.assertRaises(InterruptedError):
            life.arm_completed()
        self.assertEqual(life.state, 'ABORT_RESERVED')

    def test_term_between_arm_check_and_assignment_wins(self):
        class Interleaved(supervisor._WorkerLifecycle):
            def __setattr__(self, name, value):
                if name == 'state' and value == 'COMPLETED_HANDOFF':
                    self.on_term(signal.SIGTERM, None)
                super().__setattr__(name, value)
        life = Interleaved()
        with self.assertRaises(InterruptedError):
            life.arm_completed()
        self.assertEqual(life.state, 'ABORT_RESERVED')

    def test_term_after_arm_is_completed_exit_not_abort_reservation(self):
        life = supervisor._WorkerLifecycle()
        life.arm_completed()
        life.on_term(signal.SIGTERM, None)
        self.assertFalse(life.shutdown_requested())
        self.assertEqual(supervisor._park_worker(life, Control()), 0)
        self.assertEqual(life.exit_reason, 'COMPLETED_TERM')

    def test_installation_precedes_setup_ready_and_go(self):
        code, life, call = self.run_main(Control([b'']))
        self.assertEqual(code, 1)
        self.assertEqual(life.exit_reason, 'PARENT_EOF_BEFORE_GO')
        call.assert_not_called()
        control = Control([b''])
        self.run_main(control)
        self.assertEqual(control.events, ['install', 'setup', 'write', 'read'])
        self.assertEqual(control.messages()[0]['type'], 'READY')

    def test_install_failure_propagates_without_claiming_reservation(self):
        control = Control()
        control.install_term = Mock(side_effect=OSError('synthetic installation failure'))
        with self.assertRaises(OSError):
            self.run_main(control)
        self.assertEqual(control.events, [])

    def test_shutdown_before_ready_suppresses_ready_and_execute(self):
        control = Control([None, b''])
        original = control.setup
        def setup():
            pid = original(); control.term(); return pid
        control.setup = setup
        code, life, call = self.run_main(control)
        self.assertEqual(code, 1)
        self.assertEqual(life.first_error, 'InterruptedError')
        self.assertEqual([m['type'] for m in control.messages()], ['ERROR'])
        call.assert_not_called()

    def test_shutdown_while_waiting_go_never_acquires(self):
        control = Control()
        control.reads = [lambda: control.term(), None, b'']
        code, life, call = self.run_main(control)
        self.assertEqual(code, 1)
        self.assertFalse(life.acquisition_possible)
        call.assert_not_called()

    def test_shutdown_with_complete_go_still_suppresses_execute(self):
        f = self.fixture(); control = Control()
        def go_and_term():
            control.term(); return self.go(f)
        control.reads = [go_and_term, b'']
        _, life, call = self.run_main(control)
        self.assertFalse(life.acquisition_possible)
        call.assert_not_called()

    def test_reserved_worker_drains_queued_go_without_early_exit(self):
        f = self.fixture(); control = Control()
        control.reads = [lambda: control.term(), self.go(f), None, b'']
        code, life, call = self.run_main(control)
        self.assertEqual(code, 1)
        self.assertEqual(control.events.count('read'), 4)
        self.assertEqual(life.exit_reason, 'PARENT_EOF')
        self.assertEqual(life.first_error, 'InterruptedError')
        call.assert_not_called()

    def test_go_wait_timeouts_and_fragments_do_not_reset_absolute_bounds(self):
        f = self.fixture(); raw = self.go(f)
        control = Control([None, raw[:8], None, raw[8:]])
        control.reads.append(lambda: control.term())
        code, _, call = self.run_main(control)
        self.assertEqual(code, 0)
        self.assertEqual(call.call_args.kwargs['startup_deadline'], 3)
        self.assertEqual(call.call_args.kwargs['total_deadline'], 20)

    def test_malformed_go_reserves_without_launch(self):
        for raw in (b'bad\n', b'{"type":"OTHER"}\n', b'{}\n{}\n', b'x'*65537):
            with self.subTest(raw_length=len(raw)):
                code, life, call = self.run_main(Control([raw, None, b'']))
                self.assertEqual(code, 1)
                self.assertIsNotNone(life.first_error)
                self.assertFalse(life.acquisition_possible)
                call.assert_not_called()

    def test_setup_error_and_failed_error_publication_still_park(self):
        control = Control([None, b''], setup_error=ValueError('synthetic setup error'),
                          write_action=Mock(side_effect=BrokenPipeError('synthetic report failure')))
        code, life, call = self.run_main(control)
        self.assertEqual(code, 1)
        self.assertEqual(life.first_error, 'ValueError')
        self.assertEqual(life.reporting_error, 'BrokenPipeError')
        self.assertEqual(control.events.count('read'), 2)
        call.assert_not_called()

    def test_blocked_error_write_is_one_observation_not_an_infinite_retry(self):
        control = Control([b''], setup_error=ValueError(), write_action=lambda raw: None)
        _, life, _ = self.run_main(control)
        self.assertEqual(control.events.count('write'), 1)
        self.assertEqual(life.reporting_error, 'OSError')

    def test_execution_exception_preserved_through_term_and_parent_loss(self):
        f = self.fixture(); control = Control([self.go(f)])
        control.reads.extend([lambda: control.term(), None, b''])
        code, life, _ = self.run_main(control, Mock(side_effect=ValueError('synthetic original')))
        self.assertEqual(code, 1)
        self.assertEqual(life.first_error, 'ValueError')
        self.assertTrue(life.acquisition_possible)
        self.assertEqual(life.exit_reason, 'PARENT_EOF')
        self.assertNotIn('DONE', [m['type'] for m in control.messages()])

    def test_shutdown_before_done_suppresses_scientific_handoff(self):
        f = self.fixture(); control = Control([self.go(f), b''])
        def execute(*args, **kwargs):
            control.term(); return {}
        code, life, _ = self.run_main(control, execute)
        self.assertEqual(code, 1)
        self.assertEqual(life.first_error, 'InterruptedError')
        self.assertNotIn('DONE', [m['type'] for m in control.messages()])

    def test_partial_and_failed_done_never_arm_completion(self):
        for mode in ('partial_term', 'full_write_term', 'failed_write'):
            with self.subTest(mode=mode):
                f = self.fixture(); control = Control([self.go(f), b''])
                def write(raw):
                    if b'"type":"DONE"' in raw:
                        if mode == 'failed_write':
                            raise BrokenPipeError('synthetic DONE failure')
                        control.term()
                        return 4 if mode == 'partial_term' else len(raw)
                    return len(raw)
                control.write_action = write
                code, life, _ = self.run_main(control)
                self.assertEqual(code, 1)
                self.assertIn(life.first_error, ('InterruptedError', 'BrokenPipeError'))
                self.assertNotEqual(life.term_state, 'COMPLETED_HANDOFF')

    def test_shutdown_after_emission_before_arming_wins(self):
        f = self.fixture(); control = Control([self.go(f), b''])
        class BeforeArm(supervisor._WorkerLifecycle):
            def arm_completed(self):
                self.on_term(signal.SIGTERM, None)
                return super().arm_completed()
        code, life, _ = self.run_main(control, lifecycle=BeforeArm())
        self.assertEqual(code, 1)
        self.assertEqual(life.first_error, 'InterruptedError')
        self.assertIn('DONE', [m['type'] for m in control.messages()])

    def test_fully_armed_done_then_term_exits_normally(self):
        f = self.fixture(); control = Control([self.go(f)])
        control.reads.append(lambda: control.term())
        code, life, _ = self.run_main(control)
        self.assertEqual(code, 0)
        self.assertEqual(life.term_state, 'COMPLETED_HANDOFF')
        self.assertIsNone(life.first_error)

    def test_parent_loss_after_possible_acquisition_is_not_clean_success(self):
        for ending in (b'', OSError('synthetic control failure'), b'unexpected'):
            with self.subTest(ending=type(ending).__name__):
                f = self.fixture(); control = Control([self.go(f), ending])
                code, life, call = self.run_main(control)
                self.assertEqual(code, 1)
                self.assertTrue(life.acquisition_possible)
                call.assert_called_once()
                self.assertIn(life.exit_reason, ('PARENT_EOF', 'CONTROL_PIPE_ERROR', 'UNEXPECTED_CONTROL'))

    def test_abort_parking_survives_term_and_timeout_until_explicit_parent_loss(self):
        life = supervisor._WorkerLifecycle(); life.reserve()
        control = Control([None, InterruptedError(), None, b''])
        control.handler = life.on_term
        control.reads.insert(0, lambda: control.term())
        self.assertEqual(supervisor._park_worker(life, control), 1)
        self.assertEqual(control.events.count('read'), 5)
        self.assertEqual(life.term_state, 'ABORT_RESERVED')

    def test_actual_worker_writer_handoff_with_genuine_entry_and_terminal_shortcut(self):
        f = self.fixture(); f.process.pid = terminal_fixtures.CHILD_PID
        control = Control([self.go(f)])
        control.reads.append(lambda: control.term())
        def execute(plan, bounds, emit, **kwargs):
            return worker.execute_worker(plan, bounds, emit,
                process_factory=f.process_factory, transport_factory=f.transport_factory, **kwargs)
        code, life, _ = self.run_main(control, execute)
        self.assertEqual(code, 0)
        messages = control.messages()
        done = next(m for m in messages if m['type'] == 'DONE')
        payload = {k:v for k,v in done.items() if k != 'type'}
        worker.validate_worker_result(f.plan, payload)
        worker.validate_cleanup_handoff(f.plan, payload,
            worker_pid=terminal_fixtures.WORKER_PID, child_pid=f.process.pid,
            token=terminal_fixtures.TOKEN)
        # Actual lifecycle messages, assessment and writer receipt through the
        # unchanged production supervisor; only scheduling/OS operations are fake.
        ops = terminal_fixtures.Operations(f.plan)
        ops.messages = [(index*.05+.01, msg) for index,msg in enumerate(messages)]
        with patch.object(supervisor.os, 'urandom', return_value=bytes.fromhex(terminal_fixtures.TOKEN)):
            result = supervisor.supervise(f.plan, terminal_fixtures.BOUNDS, ops=ops, clock=ops.clock)
        self.assertTrue(result['terminal_cleanup'])
        self.assertTrue(result['worker_reaped'])
        self.assertTrue(result['normal_finalization'])
        self.assertEqual(life.exit_reason, 'COMPLETED_TERM')


class WorkerControlTests(unittest.TestCase):
    def test_genuine_setup_uses_only_owned_pipes_and_existing_file_limit(self):
        import resource
        control = supervisor._WorkerControl()
        with patch.object(supervisor.os, 'getpid', return_value=9876), \
                patch.object(supervisor.os, 'getpgrp', return_value=9876), \
                patch.object(supervisor.os, 'getsid', return_value=9876), \
                patch.object(supervisor.os, 'set_blocking') as blocking, \
                patch.object(resource, 'setrlimit') as limit:
            self.assertEqual(control.setup(), 9876)
        self.assertEqual([call.args for call in blocking.call_args_list], [(0, False), (1, False)])
        limit.assert_called_once_with(resource.RLIMIT_FSIZE,
                                      (supervisor.io.MAX_BYTES, supervisor.io.MAX_BYTES))

    def test_error_write_is_small_even_before_nonblocking_setup(self):
        control = supervisor._WorkerControl()
        with patch.object(control, '_ready', return_value=True), \
                patch.object(supervisor.os, 'write', return_value=supervisor.select.PIPE_BUF) as write:
            control.write(b'x' * (supervisor.select.PIPE_BUF * 2))
        self.assertEqual(len(write.call_args.args[1]), supervisor.select.PIPE_BUF)

    def test_term_install_is_caught_only_when_explicitly_called(self):
        control = supervisor._WorkerControl()
        handler = supervisor._WorkerLifecycle().on_term
        with patch.object(supervisor.signal, 'signal') as install:
            control.install_term(handler)
        install.assert_called_once_with(signal.SIGTERM, handler)

    def test_poll_recomputes_remaining_interval_after_interruption(self):
        control = supervisor._WorkerControl()
        control.clock = Mock(side_effect=[0, 0, .04, .1])
        with patch.object(supervisor.select, 'select', side_effect=InterruptedError()) as select:
            self.assertFalse(control._ready(True))
        self.assertEqual(select.call_count, 2)
        self.assertAlmostEqual(select.call_args_list[0].args[3], .1)
        self.assertAlmostEqual(select.call_args_list[1].args[3], .06)

    def test_restarted_selector_timeout_is_a_finite_observation(self):
        control = supervisor._WorkerControl()
        control.clock = Mock(side_effect=[0, 0])
        with patch.object(supervisor.select, 'select', return_value=([], [], [])) as select:
            self.assertIsNone(control.read())
        self.assertLessEqual(select.call_args.args[3], .1)

    def test_read_write_races_and_eof_are_explicit_injected_operations(self):
        control = supervisor._WorkerControl()
        with patch.object(control, '_ready', return_value=True):
            for error in (BlockingIOError(), InterruptedError()):
                with self.subTest(operation='read', error=type(error).__name__):
                    with patch.object(supervisor.os, 'read', side_effect=error):
                        self.assertIsNone(control.read())
                with self.subTest(operation='write', error=type(error).__name__):
                    with patch.object(supervisor.os, 'write', side_effect=error):
                        self.assertIsNone(control.write(b'x'))
            with patch.object(supervisor.os, 'read', return_value=b''):
                self.assertEqual(control.read(), b'')
            with patch.object(supervisor.os, 'write', return_value=0):
                with self.assertRaises(EOFError):
                    control.write(b'x')
