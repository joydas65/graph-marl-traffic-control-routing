"""Completion publication/arming schedules using actual components, no native IO.

Worker publication and parent reception are deterministic separate schedules:
recorded genuine worker messages enter the actual supervisor. Every native
operation is injected; these checks do not establish native timing behavior.
"""
import copy
from dataclasses import asdict, replace
import errno
import hashlib
import json
import resource
import signal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.b0.od_integration_v1 import native_supervisor as supervisor
from scripts.b0.od_integration_v1 import native_worker as worker
import test_b0_od_integration_live_binding as fixtures
import test_b0_od_integration_terminal_cleanup as terminal


class ComposedExit(BaseException):
    """End only the injected scheduler after actual _park_worker returned."""
    def __init__(self, code):
        self.code = code


class RecordingControl:
    """Transparent ordinary-flow observation; never completes partial writes."""
    def __init__(self, target, trace):
        self.target, self.trace = target, trace
        self.clock = target.clock
    def install_term(self, handler):
        return self.target.install_term(handler)
    def setup(self):
        return self.target.setup()
    def read(self):
        self.trace.append(('record_read',))
        return self.target.read()
    def write(self, raw):
        try:
            count = self.target.write(raw)
        except BaseException as error:
            self.trace.append(('record_write_error', type(error).__name__))
            raise
        self.trace.append(('record_write', len(raw), count))
        return count


class WorkerSchedule:
    """Actual control implementation with only its native operations replaced."""
    def __init__(self, fixture, *, wrapped=False, hook=None, genuine=True):
        self.fixture, self.wrapped, self.hook, self.genuine = fixture, wrapped, hook, genuine
        self.trace, self.raw, self.messages = [], bytearray(), []
        self.pending = bytearray()
        self.now, self.read_count, self.done_visible = 0.0, 0, False
        self.handler = None
        self.go_protocol = supervisor.COMPLETION_PROTOCOL
        self.park_callback = None
        self.bounds = supervisor.SupervisorBounds(fixtures.BOUNDS, 2, 20, 3, 4)
        schedule = self

        class Lifecycle(supervisor._WorkerLifecycle):
            def forward(self):
                if schedule.done_visible and self.state == 'PRE_COMPLETION':
                    schedule.event('post_write_check')
                return super().forward()
            def arm_completed(self):
                schedule.event('before_arm')
                result = super().arm_completed()
                schedule.event('after_arm')
                return result
        self.life = Lifecycle()

    def clock(self):
        return self.now

    def event(self, name, **values):
        self.trace.append((name, self.life.state, self.life.term_state))
        if self.hook is not None:
            return self.hook(self, name, **values)

    def term(self):
        self.handler(signal.SIGTERM, None)

    def run(self):
        f = self.fixture
        f.process.pid = terminal.CHILD_PID
        control = supervisor._WorkerControl()
        control.clock = self.clock
        observed = RecordingControl(control, self.trace) if self.wrapped else control
        real_read, real_write = supervisor.os.read, supervisor.os.write
        go = dict(type='GO', plan=asdict(f.plan), bounds=asdict(self.bounds),
                  startup_deadline=fixtures.BOUNDS.startup, total_deadline=20,
                  cleanup_token=terminal.TOKEN)
        if self.go_protocol is not None:
            go['completion_protocol'] = self.go_protocol
        def install(signum, handler):
            assert signum == signal.SIGTERM
            assert handler.__self__ is self.life
            self.handler = handler
        def read(fd, count):
            if fd != 0:
                return real_read(fd, count)
            self.read_count += 1
            if self.read_count == 1:
                return (json.dumps(go)+'\n').encode()
            if self.life.state == 'COMPLETED_HANDOFF':
                self.event('park_completed')
                if self.park_callback is not None:
                    return self.park_callback(self)
                self.term()
                return None
            return b''
        def write(fd, raw):
            if fd != 1:
                return real_write(fd, raw)
            if raw.startswith(b'{"type":"DONE",'):
                self.event('before_done_write')
            if raw.startswith(b'{"type":"COMPLETION_ARMED",'):
                self.event('before_marker_write')
            changed = self.event('write', raw=raw)
            if changed is not None:
                raw = raw[:changed]
            self.pending.extend(raw)
            self.raw.extend(raw)
            while b'\n' in self.pending:
                line, tail = bytes(self.pending).split(b'\n', 1)
                self.pending[:] = tail
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeError):
                    self.event('invalid_frame')
                    continue
                self.messages.append(message)
                if message['type'] == 'DONE':
                    self.done_visible = True
                    self.event('done_visible')
                elif message['type'] not in ('READY','CHILD','PHASE','FIRST_FAILURE','ERROR'):
                    self.event('marker_visible')
            return len(raw)
        def execute(plan, runtime, emit, **kwargs):
            if not self.genuine:
                # Explicit operational-only schema fixture. Never submitted to
                # scientific acceptance/readback; those tests use execute_worker.
                emit(dict(type='CHILD', pid=terminal.CHILD_PID))
                for phase in ('CONNECT','RUN','FINALIZE'):
                    emit(dict(type='PHASE', phase=phase))
                return terminal.done_payload(plan, kwargs['cleanup_token'])
            return worker.execute_worker(plan, runtime, emit,
                process_factory=f.process_factory, transport_factory=f.transport_factory, **kwargs)
        with patch.object(supervisor.signal, 'signal', side_effect=install), \
                patch.object(supervisor.os, 'getpid', return_value=terminal.WORKER_PID), \
                patch.object(supervisor.os, 'getpgrp', return_value=terminal.WORKER_PID), \
                patch.object(supervisor.os, 'getsid', return_value=terminal.WORKER_PID), \
                patch.object(supervisor.os, 'set_blocking'), \
                patch.object(resource, 'setrlimit'), \
                patch.object(supervisor.os, 'read', side_effect=read), \
                patch.object(supervisor.os, 'write', side_effect=write), \
                patch.object(supervisor.select, 'select', side_effect=lambda r,w,x,t:(r,w,[])):
            try:
                self.code = supervisor.worker_main(ops=observed, lifecycle=self.life, execute=execute)
            except ComposedExit as completed:
                self.code = completed.code
        return self


class ParentSchedule:
    """Native observations are injected; supervision/order/deadlines are real."""
    def __init__(self, plan, messages, *, before_receive=None, after_receive=None,
                 signal_error=None, terminal_observed=True, tail=None):
        self.plan, self.messages = plan, copy.deepcopy(messages)
        self.before_receive, self.after_receive = before_receive, after_receive
        self.signal_error, self.terminal_observed = signal_error, terminal_observed
        self.now, self.index, self.stopped = 0.0, 0, False
        self.handle = SimpleNamespace(pid=terminal.WORKER_PID, returncode=None)
        self.log, self.deadlines = [], []
        self.disabled = False
        self.tail = dict(state='QUIET') if tail is None else tail
    def clock(self):
        return self.now
    def bootstrap(self, plan, bounds):
        assert plan is self.plan
        return self.handle
    def verify_scope(self, handle):
        return handle is self.handle
    def send(self, handle, message, deadline):
        self.go = copy.deepcopy(message)
    def receive(self, handle, deadline):
        self.deadlines.append(deadline)
        if self.before_receive:
            self.before_receive(self, self.index)
        if not self.messages:
            self.now = deadline
            return None
        value = self.messages.pop(0)
        self.index += 1
        self.log.append(('receive', value.get('type') if isinstance(value, dict) else 'MALFORMED'))
        if self.after_receive:
            self.after_receive(self, value)
        return value
    def observe_worker(self, handle):
        if self.terminal_observed and any(x == ('signal','TERM') for x in self.log):
            return dict(state='TERMINAL', pid=handle.pid, exit_code=0)
        return dict(state='NO_STATUS')
    def signal_group(self, handle, sig):
        assert not self.disabled
        self.log.append(('signal',sig))
        if self.signal_error:
            raise self.signal_error
    signal_worker = signal_group
    def completion_tail(self, handle, deadline):
        self.log.append(('tail',deadline,self.now))
        if isinstance(self.tail, BaseException):
            raise self.tail
        return copy.deepcopy(self.tail)
    def pause(self, deadline):
        self.log.append(('grace', deadline, self.now))
        self.now = deadline
    def disable_signalling(self, handle):
        self.disabled = True
        self.log.append(('disable',))
    def reap(self, handle, deadline):
        assert self.disabled
        self.log.append(('reap',deadline,self.now))
        handle.returncode = 0
        return 0
    def finish(self, handle):
        self.log.append(('finish',))
    def run(self, bounds):
        with patch.object(supervisor.os, 'urandom', return_value=bytes.fromhex(terminal.TOKEN)):
            return supervisor.supervise(self.plan, bounds, ops=self, clock=self.clock,
                                        cancelled=lambda:self.stopped)


class CompletionArmingTests(unittest.TestCase):
    def fixture(self, **kwargs):
        value = fixtures.Fixture(**kwargs)
        self.addCleanup(value.close)
        return value

    def actual(self, *, outcome='valid', wrapped=False):
        options = {'valid': {}, 'inconclusive': {'stderr': b'Warning: Synthetic unknown warning.\n'},
                   'fail': {'stderr': b'Error: Synthetic independent contradiction.\n', 'missing': True}}
        return WorkerSchedule(self.fixture(**options[outcome]), wrapped=wrapped).run()

    def marker(self, schedule):
        return next(v for v in schedule.messages if v['type'] not in
                    ('READY','CHILD','PHASE','FIRST_FAILURE','DONE','ERROR'))

    def operational(self, **kwargs):
        return WorkerSchedule(self.fixture(), genuine=False, **kwargs).run()

    def test_actual_completed_outcomes_keep_independent_scientific_meaning(self):
        for outcome, status in (('valid', None), ('fail', 'FAIL'), ('inconclusive', 'INCONCLUSIVE')):
            for wrapped in (False, True):
                with self.subTest(outcome=outcome, wrapped=wrapped):
                    schedule = self.actual(outcome=outcome, wrapped=wrapped)
                    self.assertEqual(schedule.code, 0)
                    self.assertEqual(schedule.life.exit_reason, 'COMPLETED_TERM')
                    self.assertEqual(schedule.life.term_state, 'COMPLETED_HANDOFF')
                    marker = self.marker(schedule)
                    types = [v['type'] for v in schedule.messages]
                    self.assertEqual(types[-2:], ['DONE', marker['type']])
                    def before(ops, index):
                        if index == len(schedule.messages)-1:
                            self.assertFalse(any(v[0] == 'signal' for v in ops.log))
                            self.assertEqual(ops.log[-1], ('receive','DONE'))
                    ops = ParentSchedule(schedule.fixture.plan, schedule.messages, before_receive=before)
                    result = ops.run(schedule.bounds)
                    self.assertTrue(result['normal_finalization'])
                    self.assertTrue(result['terminal_cleanup'])
                    self.assertEqual([v for v in ops.log if v[0] == 'signal'], [('signal','TERM')])
                    self.assertEqual(result['worker_result']['assessment']['stop_status'], status)
                    payload = worker.validate_worker_result(schedule.fixture.plan, result['worker_result'])
                    self.assertEqual(payload['evidence_kind'], 'SYNTHETIC')
                    self.assertFalse(payload['ready_to_run'])
                    self.assertEqual(len(schedule.fixture.process.waits), 1)
                    self.assertEqual(result['status'], 'WORKER_COMPLETED' if status is None else 'COMPLETED_WITH_FAILURE')

    def test_prearming_shutdown_schedules_never_emit_an_armed_marker(self):
        for point in ('before_done_write','done_visible','post_write_check','before_arm'):
            for wrapped in (False, True):
                with self.subTest(point=point, wrapped=wrapped):
                    fired = []
                    def hook(schedule, event, **values):
                        if event == point and not fired:
                            fired.append(event)
                            schedule.term()
                    schedule = WorkerSchedule(self.fixture(), wrapped=wrapped, hook=hook, genuine=False).run()
                    self.assertEqual(fired, [point])
                    self.assertEqual(schedule.code, 1)
                    self.assertEqual(schedule.life.term_state, 'PRE_COMPLETION')
                    self.assertEqual(schedule.life.first_error, 'InterruptedError')
                    self.assertNotIn('COMPLETION_ARMED', [v['type'] for v in schedule.messages])

    def test_successful_arming_precedes_marker_and_does_not_ignore_completed_term(self):
        for point in ('after_arm','before_marker_write','marker_visible'):
            for wrapped in (False,True):
                with self.subTest(point=point,wrapped=wrapped):
                    fired = []
                    def hook(schedule, event, **values):
                        if event == point and not fired:
                            fired.append(event)
                            self.assertEqual(schedule.life.state, 'COMPLETED_HANDOFF')
                            schedule.term()
                    schedule = WorkerSchedule(self.fixture(), wrapped=wrapped,hook=hook,genuine=False).run()
                    self.assertEqual(fired, [point])
                    self.assertEqual(schedule.code, 0)
                    self.assertEqual(schedule.life.term_state, 'COMPLETED_HANDOFF')
                    self.marker(schedule)

    def test_marker_reporting_broken_pipe_preserves_visible_failure(self):
        def hook(schedule, event, **values):
            if event == 'before_marker_write':
                raise BrokenPipeError('synthetic marker failure')
        schedule = WorkerSchedule(self.fixture(), hook=hook, genuine=False).run()
        self.assertEqual(schedule.code, 1)
        self.assertEqual(schedule.life.first_error, 'BrokenPipeError')
        self.assertEqual([v['type'] for v in schedule.messages][-2:], ['DONE','ERROR'])

    def test_later_fresh_readback_disagreement_is_not_hidden_by_prior_acceptance(self):
        schedule = self.actual(outcome='inconclusive')
        ops = ParentSchedule(schedule.fixture.plan, schedule.messages)
        result = ops.run(schedule.bounds)
        self.assertTrue(result['normal_finalization'])
        handoff = result['worker_result']
        worker.validate_worker_result(schedule.fixture.plan, handoff)
        changed = copy.deepcopy(handoff)
        changed['assessment']['stop_status'] = 'FAIL'
        worker.validate_cleanup_handoff(schedule.fixture.plan, changed,
            worker_pid=terminal.WORKER_PID, child_pid=terminal.CHILD_PID, token=terminal.TOKEN)
        with self.assertRaisesRegex(ValueError, 'WORKER_ASSESSMENT_MISMATCH'):
            worker.validate_worker_result(schedule.fixture.plan, changed)
        worker.validate_worker_result(schedule.fixture.plan, handoff)

    def test_marker_is_explicit_bounded_and_bound_to_full_candidate(self):
        schedule = self.operational()
        marker = self.marker(schedule)
        candidate = {k:v for k,v in schedule.messages[-2].items() if k != 'type'}
        digest = lambda value:hashlib.sha256(json.dumps(value, allow_nan=False,
            sort_keys=True, separators=(',',':')).encode()).hexdigest()
        self.assertEqual(marker, dict(type='COMPLETION_ARMED',
            protocol='B0_WORKER_COMPLETION_ARMED_V1', version=1,
            run_id=schedule.fixture.plan.run_id, worker_pid=terminal.WORKER_PID,
            token=terminal.TOKEN, binding_sha256=digest(schedule.fixture.plan.binding),
            candidate_sha256=digest(candidate)))
        self.assertLessEqual(len(json.dumps(marker,separators=(',',':')).encode())+1,1024)
        self.assertEqual([v[0] for v in schedule.trace].index('done_visible') <
                         [v[0] for v in schedule.trace].index('after_arm'), True)

    def test_provisional_done_without_marker_expires_under_original_finalize_bound(self):
        schedule = self.operational()
        seen_pending = []
        def before(ops, index):
            if index == len(schedule.messages)-1:
                self.assertFalse(any(v[0] == 'signal' for v in ops.log))
                seen_pending.append(index)
        ops = ParentSchedule(schedule.fixture.plan, schedule.messages[:-1], before_receive=before)
        result = ops.run(schedule.bounds)
        self.assertTrue(seen_pending)
        self.assertEqual(result['first_failure']['code'], 'TIMEOUT')
        self.assertFalse(result['normal_finalization'])
        self.assertFalse(result['terminal_cleanup'])
        self.assertIsNone(result['worker_result'])
        self.assertIsNotNone(result['provisional_result'])
        self.assertIsNone(result['completion_armed'])
        self.assertEqual(ops.deadlines[-1], schedule.bounds.finalize)
        grace = next(v for v in ops.log if v[0] == 'grace')
        reap = next(v for v in ops.log if v[0] == 'reap')
        self.assertEqual(grace[1]-grace[2], fixtures.BOUNDS.terminate_wait)
        self.assertEqual(reap[1]-schedule.bounds.finalize, schedule.bounds.cleanup)

    def test_marker_identity_mutations_and_unknown_fields_never_complete(self):
        schedule = self.operational()
        marker = self.marker(schedule)
        mutations = dict(type='READY', protocol='UNSUPPORTED', version=2,
            run_id='other-run', worker_pid=terminal.WORKER_PID+1,
            token='f'*32, binding_sha256='0'*64, candidate_sha256='0'*64,
            unexpected='field')
        for field, value in mutations.items():
            with self.subTest(field=field):
                messages = copy.deepcopy(schedule.messages)
                messages[-1][field] = value
                result = ParentSchedule(schedule.fixture.plan,messages).run(schedule.bounds)
                self.assertFalse(result['normal_finalization'])
                self.assertFalse(result['terminal_cleanup'])
                self.assertIsNone(result['worker_result'])
        for field in marker:
            with self.subTest(missing=field):
                messages = copy.deepcopy(schedule.messages)
                del messages[-1][field]
                result = ParentSchedule(schedule.fixture.plan,messages).run(schedule.bounds)
                self.assertFalse(result['normal_finalization'])

    def test_premature_marker_duplicate_done_and_malformed_marker_are_rejected(self):
        schedule = self.operational()
        done, marker = schedule.messages[-2:]
        prefixes = schedule.messages[:-2]
        cases = {'premature': [marker,done], 'duplicate_done':[done,done,marker],
                 'wrong_order':[done,dict(type='PHASE',phase='FINALIZE'),marker],
                 'malformed':[done,[]]}
        for name, tail in cases.items():
            with self.subTest(case=name):
                result = ParentSchedule(schedule.fixture.plan,prefixes+tail).run(schedule.bounds)
                self.assertFalse(result['normal_finalization'])
                self.assertFalse(result['terminal_cleanup'])
                self.assertIsNotNone(result['first_failure'])

    def test_partial_done_with_sticky_term_never_publishes_marker(self):
        fired = []
        def hook(schedule, event, **values):
            if event == 'write' and values['raw'].startswith(b'{"type":"DONE",') and not fired:
                fired.append(True)
                schedule.term()
                return 7
        schedule = self.operational(hook=hook)
        self.assertEqual(schedule.code,1)
        self.assertEqual(schedule.life.first_error,'InterruptedError')
        self.assertNotIn('DONE',[v['type'] for v in schedule.messages])
        self.assertNotIn('COMPLETION_ARMED',[v['type'] for v in schedule.messages])

    def test_partial_or_duplicate_trailing_notification_never_earns_completion(self):
        schedule = self.operational()
        marker = json.dumps(self.marker(schedule)).encode()+b'\n'
        for name, count in (('partial',1), ('duplicate',len(marker))):
            with self.subTest(kind=name):
                ops = ParentSchedule(schedule.fixture.plan,schedule.messages,
                    tail=dict(state='TRAILING',byte_count=count))
                result = ops.run(schedule.bounds)
                self.assertFalse(result['normal_finalization'])
                self.assertFalse(result['terminal_cleanup'])
                self.assertIsNone(result['worker_result'])
                self.assertEqual(result['child_scope'],'UNRESOLVED')

    def test_marker_tail_schema_and_transport_errors_stay_visible(self):
        schedule = self.operational()
        tails = [dict(state='TRAILING',byte_count=0), dict(state='QUIET',extra=True),
                 {}, None, BrokenPipeError('synthetic tail read failure')]
        for tail in tails:
            with self.subTest(tail=repr(tail)):
                ops = ParentSchedule(schedule.fixture.plan,schedule.messages)
                ops.tail = tail
                result = ops.run(schedule.bounds)
                self.assertFalse(result['normal_finalization'])
                self.assertIsNotNone(result['first_failure'])

    def test_cancellation_before_and_after_done_and_marker_never_accepts_science(self):
        schedule = self.operational()
        for boundary in ('before_done','after_done','before_marker','after_marker'):
            with self.subTest(boundary=boundary):
                def before(ops,index):
                    if ((boundary=='before_done' and index==len(schedule.messages)-2) or
                            (boundary=='before_marker' and index==len(schedule.messages)-1)):
                        ops.stopped = True
                def after(ops,message):
                    if ((boundary=='after_done' and message.get('type')=='DONE') or
                            (boundary=='after_marker' and message.get('type')=='COMPLETION_ARMED')):
                        ops.stopped = True
                ops = ParentSchedule(schedule.fixture.plan,schedule.messages,
                    before_receive=before,after_receive=after)
                result = ops.run(schedule.bounds)
                self.assertFalse(result['normal_finalization'])
                self.assertFalse(result['terminal_cleanup'])
                self.assertIsNone(result['worker_result'])
                self.assertEqual(result['first_failure']['code'],'CANCELLED')

    def test_deadline_expiry_at_done_and_marker_readback_boundaries_is_not_reset(self):
        schedule = self.operational()
        for boundary in ('DONE','COMPLETION_ARMED'):
            with self.subTest(boundary=boundary):
                def after(ops,message):
                    if message.get('type') == boundary:
                        ops.now = ops.deadlines[-1]
                ops = ParentSchedule(schedule.fixture.plan,schedule.messages,after_receive=after)
                result = ops.run(schedule.bounds)
                self.assertEqual(result['first_failure']['code'],'TIMEOUT')
                self.assertFalse(result['normal_finalization'])
                self.assertFalse(result['terminal_cleanup'])
                self.assertEqual(result['late_messages'][-1]['type'],boundary)
                self.assertEqual(ops.deadlines[-1],schedule.bounds.finalize)

    def test_valid_marker_without_terminal_observation_preserves_escalation(self):
        schedule = self.operational()
        ops = ParentSchedule(schedule.fixture.plan,schedule.messages,terminal_observed=False)
        result = ops.run(schedule.bounds)
        self.assertFalse(result['terminal_cleanup'])
        self.assertEqual([v for v in ops.log if v[0]=='signal'],[('signal','TERM'),('signal','KILL')])
        self.assertTrue(result['scope_signalling_disabled'])
        self.assertLess(ops.log.index(('disable',)),next(i for i,v in enumerate(ops.log) if v[0]=='reap'))

    def test_attempted_signal_error_keeps_actual_exception_and_errno(self):
        schedule = self.operational()
        ops = ParentSchedule(schedule.fixture.plan,schedule.messages,
                             signal_error=PermissionError(errno.EPERM,'synthetic denial'))
        result = ops.run(schedule.bounds)
        errors = [v for v in result['findings'] if v['code']=='SIGNAL_UNRESOLVED']
        self.assertTrue(errors)
        self.assertEqual(errors[0]['exception'],'PermissionError')
        self.assertEqual(errors[0]['errno'],errno.EPERM)
        self.assertIsNotNone(result['first_failure'])

    def test_historical_done_only_input_is_not_rewritten_or_promoted(self):
        schedule = self.operational()
        historical = copy.deepcopy(schedule.messages[:-1])
        before = copy.deepcopy(historical)
        result = ParentSchedule(schedule.fixture.plan,historical).run(schedule.bounds)
        self.assertEqual(historical,before)
        self.assertFalse(result['normal_finalization'])
        self.assertIsNone(result['completion_armed'])
        self.assertIsNone(result['worker_result'])

    def test_absent_or_legacy_go_protocol_never_reaches_executor(self):
        for protocol in (None, 'LEGACY_DONE_ONLY', 1, True):
            with self.subTest(protocol=protocol):
                schedule = WorkerSchedule(self.fixture(), genuine=False)
                schedule.go_protocol = protocol
                schedule.run()
                self.assertEqual(schedule.code,1)
                self.assertFalse(schedule.life.acquisition_possible)
                self.assertEqual([v['type'] for v in schedule.messages],['READY','ERROR'])
                self.assertEqual(schedule.life.first_error,'ValueError')

    def test_cancellation_during_existing_grace_revokes_previously_armed_completion(self):
        schedule = self.operational()
        ops = ParentSchedule(schedule.fixture.plan,schedule.messages)
        original = ops.completion_tail
        def tail(handle,deadline):
            value = original(handle,deadline)
            ops.stopped = True
            return value
        ops.completion_tail = tail
        result = ops.run(schedule.bounds)
        self.assertIsNotNone(result['completion_armed'])
        self.assertFalse(result['normal_finalization'])
        self.assertFalse(result['terminal_cleanup'])
        self.assertIsNone(result['worker_result'])
        self.assertEqual(result['first_failure']['code'],'CANCELLED')

    def test_marker_boolean_and_numeric_identity_types_are_not_interchangeable(self):
        schedule = self.operational()
        for field, value in (('version',True), ('version',1.0),
                             ('worker_pid',float(terminal.WORKER_PID)),
                             ('token',None),('candidate_sha256',[])):
            with self.subTest(field=field,value=value):
                messages = copy.deepcopy(schedule.messages)
                messages[-1][field] = value
                result = ParentSchedule(schedule.fixture.plan,messages).run(schedule.bounds)
                self.assertFalse(result['normal_finalization'])
                self.assertIsNone(result['worker_result'])

    def test_actual_worker_and_parent_call_stacks_compose_at_armed_park_boundary(self):
        for wrapped in (False,True):
            with self.subTest(wrapped=wrapped):
                schedule = WorkerSchedule(self.fixture(),wrapped=wrapped)
                composed = {}
                def park(actual):
                    self.assertIs(actual,schedule)
                    self.assertEqual(schedule.life.state,'COMPLETED_HANDOFF')
                    self.assertIsNone(schedule.life.term_state)
                    ops = ParentSchedule(schedule.fixture.plan,schedule.messages)
                    exited = []
                    signal_operation = ops.signal_group
                    def deliver(handle,sig):
                        signal_operation(handle,sig)
                        self.assertEqual(sig,'TERM')
                        schedule.term()  # Exact installed handler; no OS signal.
                    def pause(deadline):
                        class NoReads:
                            def read(self):
                                raise AssertionError('completed TERM must need no further IO')
                        # Re-enter the actual ordinary-flow decision, not a
                        # hardcoded clean worker exit. No wait/thread is involved.
                        code = supervisor._park_worker(schedule.life,NoReads())
                        exited.append(code)
                        self.assertEqual(code,0)
                        self.assertEqual(schedule.life.exit_reason,'COMPLETED_TERM')
                        ops.now = deadline
                    def observe(handle):
                        return (dict(state='TERMINAL',pid=handle.pid,exit_code=exited[0])
                                if exited else dict(state='NO_STATUS'))
                    def reap(handle,deadline):
                        self.assertTrue(ops.disabled)
                        self.assertEqual(exited,[0])
                        handle.returncode = exited[0]
                        return exited[0]
                    ops.signal_group = deliver
                    ops.pause, ops.observe_worker, ops.reap = pause,observe,reap
                    composed['result'] = ops.run(schedule.bounds)
                    composed['log'] = ops.log
                    raise ComposedExit(exited[0])
                schedule.park_callback = park
                schedule.run()
                self.assertEqual(schedule.code,0)
                result = composed['result']
                self.assertEqual(result['status'],'WORKER_COMPLETED')
                self.assertTrue(result['terminal_cleanup'])
                self.assertEqual(result['worker_exit_code'],0)
                self.assertEqual(result['child_scope'],'REPORTED_CHILD_REAPED_AND_WORKER_REAPED')
                self.assertEqual([x for x in composed['log'] if x[0]=='signal'],[('signal','TERM')])
                payload = worker.validate_worker_result(schedule.fixture.plan,result['worker_result'])
                self.assertEqual(payload['record_kind'],'RUN')
                self.assertFalse(payload['ready_to_run'])
                self.assertEqual(len(schedule.fixture.process.waits),1)

    def test_plan_binding_disagreement_cannot_reuse_armed_message_or_readback(self):
        schedule = self.actual()
        altered = copy.deepcopy(schedule.fixture.plan.binding)
        altered['synthetic_source_disagreement'] = True
        changed_plan = replace(schedule.fixture.plan,binding=altered)
        ops = ParentSchedule(changed_plan,schedule.messages)
        result = ops.run(schedule.bounds)
        self.assertFalse(result['normal_finalization'])
        self.assertIsNone(result['worker_result'])
        candidate = {k:v for k,v in schedule.messages[-2].items() if k!='type'}
        with self.assertRaises(ValueError):
            worker.validate_worker_result(changed_plan,candidate)
