"""Terminal cleanup gates with clock/process/waitid doubles only.

No test launches a process, opens a socket, or signals an OS identity. A
synthetic worker integration uses the existing inert client/process fixture;
all nonreaping OS status observations below are explicit mocked returns.
"""
import copy
import errno
import signal
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.b0.od_integration_v1 import integration as core
from scripts.b0.od_integration_v1 import native_supervisor as supervisor
from scripts.b0.od_integration_v1 import native_worker as worker
from scripts.b0.od_integration_v1.owned_runtime import RuntimeBounds
import test_b0_od_integration_live_binding as binding_fixtures


WORKER_PID = 49152
CHILD_PID = 49153
TOKEN = '0123456789abcdef0123456789abcdef'
RUNTIME = RuntimeBounds(2, 2, 1, 1, 1, 1, 1)
BOUNDS = supervisor.SupervisorBounds(RUNTIME, 2, 20, 3, 4)


def plan():
    return SimpleNamespace(run_id='synthetic-terminal-cleanup', condition='N0',
        evidence_kind='SYNTHETIC', binding={'fixture': 'cleanup-binding-only'},
        output_directory='synthetic-test-outputs/terminal-cleanup-in-memory')


def handoff(p, token=TOKEN, child_pid=CHILD_PID):
    return dict(version=1, run_id=p.run_id, condition_label=p.condition,
        evidence_kind=p.evidence_kind, binding_sha256=core.digest(p.binding),
        output_directory=p.output_directory, worker_pid=WORKER_PID, token=token,
        child_launches=1,
        child_wait=dict(pid=child_pid, exit_code=0, wait_returned=True),
        finalization_process=dict(state='EXITED', exit_code=0))


def done_payload(p, token):
    """Explicit in-memory identities, not persisted or scientific evidence."""
    grant = dict(run_id=p.run_id, condition_label=p.condition,
        binding_sha256=core.digest(p.binding), output_directory=p.output_directory,
        expected=dict(device=1, inode=2, byte_count=None, sha256=None),
        evidence_kind=p.evidence_kind)
    receipt = dict(schema_version=1, evidence_kind=p.evidence_kind,
        ready_to_run=False, persistence_status='VERIFIED',
        output_directory=p.output_directory, name=worker.RESULT_NAME,
        format='JSON', sha256='a' * 64, byte_count=1)
    return dict(receipt=receipt, grants=[grant], child_reaped=True,
        assessment=dict(measurement_status='VALID', stop_status=None, reason_codes=[]),
        first_failure=None, cleanup_handoff=handoff(p, token))


def terminal(pid=WORKER_PID, exit_code=0):
    return dict(state='TERMINAL', pid=pid, exit_code=exit_code)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class Operations:
    """A single retained handle and FIFO messages, never an OS operation."""
    def __init__(self, p, *, observations=None, mutate=None, handoff_present=True,
                 child_reported=True, child_reaped=True, verified=True,
                 prior_failure=None, done_at=.6, reap_error=None,
                 reap_late=False, signal_errors=None, pause_action=None):
        self.plan = p
        self.clock = Clock()
        self.handle = SimpleNamespace(pid=WORKER_PID, returncode=None)
        self.observations = list(observations if observations is not None else
                                 [dict(state='NO_STATUS'), terminal()])
        self.mutate, self.handoff_present = mutate, handoff_present
        self.child_reaped, self.verified = child_reaped, verified
        self.reap_error, self.reap_late = reap_error, reap_late
        self.signal_errors = {} if signal_errors is None else signal_errors
        self.pause_action = pause_action
        self.log, self.go = [], None
        self.disabled = False
        self.reap_code = 0
        self.messages = [(.1, dict(type='READY', pid=WORKER_PID))]
        if child_reported:
            self.messages.append((.15, dict(type='CHILD', pid=CHILD_PID)))
        self.messages.extend([(.2, dict(type='PHASE', phase='CONNECT')),
                              (.3, dict(type='PHASE', phase='RUN'))])
        if prior_failure is not None:
            self.messages.append((.35, dict(type='FIRST_FAILURE', failure=prior_failure)))
        self.messages.extend([(.4, dict(type='PHASE', phase='FINALIZE')),
                              (done_at, 'DONE')])

    def bootstrap(self, p, bounds):
        assert p is self.plan
        self.log.append(('bootstrap', self.clock()))
        return self.handle

    def verify_scope(self, handle):
        assert handle is self.handle
        return self.verified

    def send(self, handle, message, deadline):
        assert handle is self.handle
        self.go = copy.deepcopy(message)
        self.log.append(('send', deadline, self.clock()))

    def receive(self, handle, deadline):
        assert handle is self.handle
        if not self.messages or self.messages[0][0] > deadline:
            self.clock.now = deadline
            return None
        at, value = self.messages.pop(0)
        self.clock.now = at
        if value == 'DONE':
            value = dict(type='DONE', **done_payload(self.plan, self.go['cleanup_token']))
            value['child_reaped'] = self.child_reaped
            if not self.handoff_present:
                value['cleanup_handoff'] = None
            if self.mutate is not None:
                self.mutate(value)
        return value

    def observe_worker(self, handle):
        assert handle is self.handle
        self.log.append(('observe', self.clock()))
        value = self.observations.pop(0) if len(self.observations) > 1 else self.observations[0]
        if callable(value):
            value = value(self)
        if isinstance(value, BaseException):
            raise value
        return copy.deepcopy(value)

    def disable_signalling(self, handle):
        assert handle is self.handle
        self.disabled = True
        self.log.append(('disable', self.clock()))

    def _signal(self, handle, sig, kind):
        assert handle is self.handle and not self.disabled
        assert handle.returncode is None
        self.log.append((kind, sig, self.clock()))
        if sig in self.signal_errors:
            raise self.signal_errors[sig]

    def signal_group(self, handle, sig):
        self._signal(handle, sig, 'group')

    def signal_worker(self, handle, sig):
        self._signal(handle, sig, 'worker')

    def pause(self, deadline):
        self.log.append(('pause', deadline, self.clock()))
        self.clock.now = deadline
        if self.pause_action is not None:
            self.pause_action(self)

    def reap(self, handle, deadline):
        assert handle is self.handle and self.disabled
        self.log.append(('reap', deadline, self.clock()))
        if self.reap_late:
            self.clock.now = deadline
        if self.reap_error is not None:
            raise self.reap_error
        self.handle.returncode = self.reap_code
        return self.reap_code

    def finish(self, handle):
        assert handle is self.handle
        self.log.append(('finish', self.clock()))


class TerminalCleanupTests(unittest.TestCase):
    def run_case(self, *, cancelled=lambda: False, **kwargs):
        p = plan()
        ops = Operations(p, **kwargs)
        with patch.object(supervisor.os, 'urandom', return_value=bytes.fromhex(TOKEN)):
            result = supervisor.supervise(p, BOUNDS, ops=ops, clock=ops.clock,
                                          cancelled=cancelled)
        return result, ops

    def signals(self, ops):
        return [item[1] for item in ops.log if item[0] in ('group', 'worker')]

    def assert_no_shortcut(self, result, ops):
        self.assertFalse(result['terminal_cleanup'])
        self.assertEqual(self.signals(ops), ['TERM', 'KILL'])
        self.assertTrue(result['scope_signalling_disabled'])

    def test_exact_terminal_and_child_wait_preserve_term_grace_then_reap(self):
        result, ops = self.run_case()
        self.assertEqual(result['status'], 'WORKER_COMPLETED')
        self.assertTrue(result['terminal_cleanup'])
        self.assertTrue(result['worker_reaped'])
        self.assertFalse(result['worker_ownership_unresolved'])
        self.assertEqual(result['child_scope'], 'REPORTED_CHILD_REAPED_AND_WORKER_REAPED')
        self.assertEqual(self.signals(ops), ['TERM'])
        kinds = [item[0] for item in ops.log]
        self.assertEqual(kinds[kinds.index('observe'):],
                         ['observe', 'group', 'pause', 'observe', 'disable', 'reap', 'finish'])
        pause = next(item for item in ops.log if item[0] == 'pause')
        reap = next(item for item in ops.log if item[0] == 'reap')
        self.assertAlmostEqual(pause[1] - pause[2], RUNTIME.terminate_wait)
        self.assertAlmostEqual(reap[1] - .6, BOUNDS.cleanup)
        self.assertEqual(ops.go['cleanup_token'], TOKEN)

    def test_nonzero_terminal_status_does_not_require_zero_for_ownership(self):
        result, ops = self.run_case(observations=[dict(state='NO_STATUS'), terminal(exit_code=-15)],
                                   pause_action=lambda o: setattr(o, 'reap_code', -15))
        self.assertTrue(result['terminal_cleanup'])
        self.assertEqual(self.signals(ops), ['TERM'])
        self.assertTrue(result['worker_reap_within_deadline'])
        self.assertIsNone(result['first_failure'])

    def test_old_unconditional_escalation_decision_then_evidence_gated_correction(self):
        # Characterize the old decision with doubles, not historical/native
        # source execution: without terminal proof the TERM/KILL rule remains.
        # The same completed child and exited worker now supply the missing
        # proof; no actual OS EPERM is needed or attempted.
        p = plan()
        old = Operations(p, signal_errors={'KILL': PermissionError(errno.EPERM, 'synthetic denial')})
        old.observe_worker = None
        before = supervisor.supervise(p, BOUNDS, ops=old, clock=old.clock)
        self.assertEqual(self.signals(old), ['TERM', 'KILL'])
        self.assertEqual(before['status'], 'COMPLETED_WITH_FAILURE')
        self.assertEqual(before['first_failure']['errno'], errno.EPERM)
        after, corrected = self.run_case(signal_errors={'KILL': PermissionError(errno.EPERM, 'synthetic denial')})
        self.assertEqual(self.signals(corrected), ['TERM'])
        self.assertEqual(after['status'], 'WORKER_COMPLETED')
        self.assertTrue(after['worker_reap_within_deadline'])
        self.assertEqual(before['worker_result']['cleanup_handoff']['child_wait'],
                         after['worker_result']['cleanup_handoff']['child_wait'])

    def test_terminal_reap_exit_contradiction_stays_failure_without_new_signal(self):
        result, ops = self.run_case(observations=[dict(state='NO_STATUS'), terminal(exit_code=-15)])
        self.assertEqual(self.signals(ops), ['TERM'])
        self.assertTrue(result['worker_reaped'])
        self.assertFalse(result['worker_reap_within_deadline'])
        self.assertEqual(result['child_scope'], 'UNRESOLVED')
        self.assertEqual(result['first_failure']['code'], 'WORKER_REAP_UNRESOLVED')

    def test_missing_handoff_and_bare_reaped_boolean_are_not_proof(self):
        for flag in (True, False):
            with self.subTest(child_reaped=flag):
                result, ops = self.run_case(handoff_present=False, child_reaped=flag)
                self.assert_no_shortcut(result, ops)
                self.assertEqual(result['child_scope'], 'UNRESOLVED')
                self.assertIn('CHILD_WAIT_UNVERIFIED', [v['code'] for v in result['findings']])

    def test_unknown_child_identity_is_not_resolved_by_worker_exit(self):
        result, ops = self.run_case(child_reported=False)
        self.assert_no_shortcut(result, ops)
        self.assertEqual(result['child_scope'], 'UNRESOLVED')
        self.assertEqual(result['status'], 'INTERRUPTED')

    def test_missing_child_wait_cannot_be_replaced_by_bare_boolean(self):
        result, ops = self.run_case(mutate=lambda done: done['cleanup_handoff'].update(child_wait=None))
        self.assert_no_shortcut(result, ops)
        self.assertEqual(result['child_scope'], 'UNRESOLVED')
        self.assertIsNotNone(result['first_failure'])

    def test_every_run_and_child_binding_mutation_fails_closed(self):
        mutations = {
            'version': True, 'run_id': 'another-synthetic-run',
            'condition_label': 'D0', 'evidence_kind': 'LIVE',
            'binding_sha256': 'f' * 64, 'output_directory': 'synthetic-test-outputs/other',
            'worker_pid': WORKER_PID + 4, 'token': 'f' * 32,
            'child_launches': 2, 'child_wait': None,
            'finalization_process': {'state': 'RUNNING', 'exit_code': None},
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                def mutate(done, field=field, value=value):
                    done['cleanup_handoff'][field] = value
                result, ops = self.run_case(mutate=mutate)
                self.assert_no_shortcut(result, ops)
                self.assertEqual(result['child_scope'], 'UNRESOLVED')
                self.assertEqual(result['status'], 'INTERRUPTED')

    def test_handoff_exact_schema_missing_extra_and_non_dict_are_rejected(self):
        for variant in ('missing', 'extra', 'non-dict'):
            with self.subTest(variant=variant):
                def mutate(done):
                    if variant == 'missing':
                        done['cleanup_handoff'].pop('child_launches')
                    elif variant == 'extra':
                        done['cleanup_handoff']['unreviewed_field'] = True
                    else:
                        done['cleanup_handoff'] = ['not-a-handoff']
                result, ops = self.run_case(mutate=mutate)
                self.assert_no_shortcut(result, ops)
                self.assertEqual(result['status'], 'INTERRUPTED')

    def test_strict_child_wait_and_finalization_contradictions(self):
        changes = [('pid', CHILD_PID + 1), ('pid', WORKER_PID), ('pid', True),
                   ('exit_code', True), ('wait_returned', False),
                   ('wait_returned', 1), ('extra', 'not-approved')]
        for field, value in changes:
            with self.subTest(field=field, value=value):
                def mutate(done, field=field, value=value):
                    done['cleanup_handoff']['child_wait'][field] = value
                result, ops = self.run_case(mutate=mutate)
                self.assert_no_shortcut(result, ops)
                self.assertEqual(result['child_scope'], 'UNRESOLVED')
        for process in ({'state': 'EXITED', 'exit_code': 1},
                        {'state': 'EXITED', 'exit_code': True},
                        {'state': 'EXITED', 'exit_code': 0, 'extra': 1}):
            with self.subTest(finalization_process=process):
                result, ops = self.run_case(mutate=lambda done:
                    done['cleanup_handoff'].update(finalization_process=process))
                self.assert_no_shortcut(result, ops)

    def test_false_reaped_hint_does_not_accept_otherwise_valid_handoff(self):
        result, ops = self.run_case(child_reaped=False)
        self.assert_no_shortcut(result, ops)
        self.assertEqual(result['child_scope'], 'UNRESOLVED')

    def test_receipt_grant_and_assessment_identity_are_required_in_memory(self):
        variants = ('outer-extra', 'outer-missing', 'receipt-hash', 'receipt-directory',
                    'receipt-origin', 'grant-binding', 'grant-output-anchor',
                    'grant-count', 'assessment-shape')
        for variant in variants:
            with self.subTest(variant=variant):
                def mutate(done):
                    if variant == 'outer-extra':
                        done['unreviewed_field'] = True
                    elif variant == 'outer-missing':
                        done.pop('receipt')
                    elif variant == 'receipt-hash':
                        done['receipt']['sha256'] = 'not-a-sha256'
                    elif variant == 'receipt-directory':
                        done['receipt']['output_directory'] = 'synthetic-test-outputs/another-run'
                    elif variant == 'receipt-origin':
                        done['receipt']['evidence_kind'] = 'LIVE'
                    elif variant == 'grant-binding':
                        done['grants'][0]['binding_sha256'] = 'f' * 64
                    elif variant == 'grant-output-anchor':
                        done['grants'][0]['expected'] = None
                    elif variant == 'grant-count':
                        done['grants'].append(copy.deepcopy(done['grants'][0]))
                    else:
                        done['assessment']['measurement_status'] = 'NOT_REVIEWED'
                result, ops = self.run_case(mutate=mutate)
                self.assert_no_shortcut(result, ops)
                self.assertEqual(result['status'], 'INTERRUPTED')
                self.assertEqual(result['child_scope'], 'UNRESOLVED')

    def test_terminal_decision_reads_no_evidence_files(self):
        with patch.object(worker.io, 'readback', side_effect=AssertionError('no cleanup readback')) as readback:
            result, ops = self.run_case()
        self.assertTrue(result['terminal_cleanup'])
        self.assertEqual(self.signals(ops), ['TERM'])
        readback.assert_not_called()

    def test_second_child_message_cannot_expand_fixed_child_contract(self):
        p = plan()
        ops = Operations(p)
        ops.messages.insert(2, (.16, dict(type='CHILD', pid=CHILD_PID + 1)))
        result = supervisor.supervise(p, BOUNDS, ops=ops, clock=ops.clock)
        self.assert_no_shortcut(result, ops)
        self.assertEqual(result['status'], 'INTERRUPTED')
        self.assertEqual(result['child_scope'], 'UNRESOLVED')

    def test_running_and_unavailable_observation_retain_escalation(self):
        for observed in (dict(state='NO_STATUS'), dict(state='UNAVAILABLE', code='NO_NONREAPING_FACILITY')):
            with self.subTest(state=observed['state']):
                result, ops = self.run_case(observations=[observed])
                self.assert_no_shortcut(result, ops)
                self.assertTrue(result['worker_reaped'])

    def test_legacy_operations_without_observer_cannot_take_shortcut(self):
        p = plan()
        ops = Operations(p)
        ops.observe_worker = None
        result = supervisor.supervise(p, BOUNDS, ops=ops, clock=ops.clock)
        self.assert_no_shortcut(result, ops)

    def test_observer_exception_is_preserved_and_does_not_create_terminal_status(self):
        result, ops = self.run_case(observations=[RuntimeError('synthetic observation failure')])
        self.assert_no_shortcut(result, ops)
        self.assertEqual(result['first_failure']['code'], 'WORKER_OBSERVATION_ERROR')
        self.assertEqual(result['first_failure']['exception'], 'RuntimeError')
        self.assertEqual(result['status'], 'COMPLETED_WITH_FAILURE')

    def test_unsafe_or_contradictory_worker_status_prevents_signal_and_reap(self):
        for observed in (dict(state='UNSAFE', code='WORKER_REAPING_OWNERSHIP_LOST'),
                         dict(state='UNSAFE', code='WAITID_WRONG_PID'),
                         terminal(pid=WORKER_PID + 1), terminal(exit_code=True),
                         {'state': 'not-a-state'}, None,
                         ChildProcessError(errno.ECHILD, 'synthetic competing reaper')):
            with self.subTest(observation_type=type(observed).__name__, observation=observed):
                result, ops = self.run_case(observations=[observed])
                self.assertEqual(self.signals(ops), [])
                self.assertFalse(any(item[0] == 'reap' for item in ops.log))
                self.assertTrue(result['scope_signalling_disabled'])
                self.assertTrue(result['worker_ownership_unresolved'])
                self.assertEqual(result['child_scope'], 'UNRESOLVED')

    def test_ownership_lost_during_grace_prevents_kill_and_consuming_wait(self):
        result, ops = self.run_case(observations=[dict(state='NO_STATUS'),
            dict(state='UNSAFE', code='WORKER_REAPING_OWNERSHIP_LOST')])
        self.assertEqual(self.signals(ops), ['TERM'])
        self.assertFalse(any(item[0] == 'reap' for item in ops.log))
        self.assertTrue(result['worker_ownership_unresolved'])
        self.assertFalse(result['terminal_cleanup'])

    def test_cached_reap_or_changed_retained_pid_during_grace_blocks_all_later_authority(self):
        for attribute, value in (('returncode', 0), ('pid', WORKER_PID + 1)):
            with self.subTest(attribute=attribute):
                result, ops = self.run_case(pause_action=lambda o:
                    setattr(o.handle, attribute, value))
                self.assertEqual(self.signals(ops), ['TERM'])
                self.assertFalse(any(item[0] == 'reap' for item in ops.log))
                self.assertTrue(result['worker_ownership_unresolved'])
                self.assertEqual(result['child_scope'], 'UNRESOLVED')

    def test_unverified_group_cannot_take_shortcut_or_signal_group(self):
        result, ops = self.run_case(verified=False)
        self.assert_no_shortcut(result, ops)
        self.assertTrue(all(item[0] != 'group' for item in ops.log))
        self.assertEqual(result['child_scope'], 'UNRESOLVED')

    def test_failed_reap_never_reenables_signalling(self):
        result, ops = self.run_case(reap_error=TimeoutError('synthetic bounded wait'))
        self.assertEqual(self.signals(ops), ['TERM'])
        self.assertTrue(ops.disabled)
        self.assertFalse(result['worker_reaped'])
        self.assertEqual(result['child_scope'], 'UNRESOLVED')
        self.assertEqual(result['first_failure']['code'], 'WORKER_REAP_UNRESOLVED')
        self.assertEqual([v[0] for v in ops.log][-3:], ['disable', 'reap', 'finish'])

    def test_late_reap_retains_timeout_and_cannot_claim_bounded_child_scope(self):
        result, ops = self.run_case(reap_late=True)
        self.assertTrue(result['scope_signalling_disabled'])
        self.assertEqual(self.signals(ops), ['TERM'])
        self.assertEqual(result['first_failure']['code'], 'WORKER_REAP_UNRESOLVED')
        self.assertEqual(result['child_scope'], 'UNRESOLVED')
        self.assertNotEqual(result['status'], 'WORKER_COMPLETED')

    def test_first_worker_failure_survives_safe_terminal_cleanup(self):
        failure = dict(kind='INTEGRITY', stage='ASSESSMENT', code='SYNTHETIC_PRIOR_FAILURE')
        result, ops = self.run_case(prior_failure=failure)
        self.assertTrue(result['terminal_cleanup'])
        self.assertEqual(self.signals(ops), ['TERM'])
        self.assertEqual(result['first_failure']['code'], 'WORKER_REPORTED_FAILURE')
        self.assertEqual(result['first_failure']['worker_failure'], failure)
        self.assertEqual(result['status'], 'COMPLETED_WITH_FAILURE')

    def test_attempted_kill_permission_error_is_not_reclassified_as_success(self):
        denied = PermissionError(errno.EPERM, 'synthetic permission denied')
        result, ops = self.run_case(observations=[dict(state='NO_STATUS')], signal_errors={'KILL': denied})
        self.assert_no_shortcut(result, ops)
        self.assertEqual(result['first_failure'], dict(operation='CLEANUP',
            code='SIGNAL_UNRESOLVED', signal='KILL', exception='PermissionError', errno=errno.EPERM))
        self.assertEqual(result['status'], 'COMPLETED_WITH_FAILURE')

    def test_earlier_failure_survives_later_signal_permission_error(self):
        prior = dict(kind='INTEGRITY', code='SYNTHETIC_FIRST')
        result, ops = self.run_case(prior_failure=prior,
            observations=[dict(state='NO_STATUS')],
            signal_errors={'KILL': PermissionError(errno.EPERM, 'synthetic denied')})
        self.assert_no_shortcut(result, ops)
        self.assertEqual(result['first_failure']['worker_failure'], prior)
        later = [v for v in result['findings'] if v['code'] == 'SIGNAL_UNRESOLVED']
        self.assertEqual([(v['signal'], v['errno']) for v in later], [('KILL', errno.EPERM)])

    def test_term_permission_error_is_retained_even_when_later_kill_is_safely_skipped(self):
        result, ops = self.run_case(signal_errors={'TERM': PermissionError(errno.EPERM, 'synthetic denied')})
        self.assertTrue(result['terminal_cleanup'])
        self.assertEqual(self.signals(ops), ['TERM'])
        self.assertEqual(result['first_failure']['signal'], 'TERM')
        self.assertEqual(result['first_failure']['errno'], errno.EPERM)
        self.assertEqual(result['status'], 'COMPLETED_WITH_FAILURE')

    def test_done_at_finalization_deadline_remains_late_and_ineligible(self):
        result, ops = self.run_case(done_at=3.4)
        self.assert_no_shortcut(result, ops)
        self.assertEqual(result['first_failure']['code'], 'TIMEOUT')
        self.assertEqual(result['status'], 'INTERRUPTED')
        self.assertEqual(result['child_scope'], 'UNRESOLVED')
        self.assertFalse(result['normal_finalization'])
        self.assertEqual(len(result['late_messages']), 1)

    def test_cancellation_during_grace_does_not_use_terminal_shortcut(self):
        state = {'cancelled': False}
        result, ops = self.run_case(cancelled=lambda: state['cancelled'],
            pause_action=lambda _: state.update(cancelled=True))
        self.assert_no_shortcut(result, ops)
        self.assertEqual(result['first_failure']['code'], 'CANCELLED')
        self.assertEqual(result['child_scope'], 'UNRESOLVED')
        self.assertEqual(result['status'], 'INTERRUPTED')


class NativeNonreapingObservationTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.ops = supervisor.NativeIPC('/synthetic/python', '0' * 64, clock=self.clock)
        self.handle = SimpleNamespace(pid=WORKER_PID, returncode=None, wait=Mock(return_value=0))
        # Model the strong handle registration made by bootstrap without
        # invoking bootstrap, Popen, pipes, client code or filesystem output.
        self.ops._handles.append(self.handle)
        self.ops._handle_pids[id(self.handle)] = WORKER_PID
        self.ops._verified_handles.add(id(self.handle))
        self.addCleanup(patch.stopall)
        patch.object(supervisor.signal, 'getsignal', return_value=signal.SIG_DFL).start()
        self.group = patch.object(supervisor.os, 'killpg').start()
        self.single = patch.object(supervisor.os, 'kill').start()
        # Platforms without waitid still exercise the production capability
        # probe through an explicitly supplied mocked facility and constants.
        constants = dict(P_PID=101, WEXITED=2, WNOHANG=4, WNOWAIT=8,
                         CLD_EXITED=1, CLD_KILLED=2, CLD_DUMPED=3)
        for name, value in constants.items():
            patch.object(supervisor.os, name, value, create=True).start()
        self.waitid = patch.object(supervisor.os, 'waitid', create=True).start()

    def status(self, pid=WORKER_PID, code=1, status=0):
        return SimpleNamespace(si_pid=pid, si_code=code, si_status=status)

    def assert_observation_only(self):
        self.group.assert_not_called()
        self.single.assert_not_called()
        self.handle.wait.assert_not_called()

    def test_exact_terminal_waitid_is_nonblocking_nonconsuming_and_worker_only(self):
        self.waitid.return_value = self.status()
        self.assertEqual(self.ops.observe_worker(self.handle), terminal())
        self.waitid.assert_called_once_with(101, WORKER_PID, 2 | 4 | 8)
        self.assert_observation_only()
        self.assertIsNone(self.handle.returncode)

    def test_all_terminal_exit_forms_use_exact_worker_status(self):
        for code, status, expected in ((1, 7, 7), (2, 15, -15), (3, 9, -9)):
            with self.subTest(code=code):
                self.waitid.return_value = self.status(code=code, status=status)
                self.assertEqual(self.ops.observe_worker(self.handle), terminal(exit_code=expected))
                self.assert_observation_only()

    def test_no_status_is_not_terminal(self):
        self.waitid.return_value = None
        self.assertEqual(self.ops.observe_worker(self.handle)['state'], 'NO_STATUS')
        self.assert_observation_only()

    def test_stopped_continued_and_invalid_exit_ranges_are_not_terminal(self):
        for code, status in ((4, 19), (5, 19), (6, 18), (1, -1), (1, 256), (2, 0)):
            with self.subTest(code=code, status=status):
                self.waitid.return_value = self.status(code=code, status=status)
                self.assertEqual(self.ops.observe_worker(self.handle)['state'], 'NO_STATUS')
                self.assert_observation_only()

    def test_bool_status_fields_are_not_integer_terminal_evidence(self):
        for code, status in ((True, 0), (1, True)):
            with self.subTest(code=code, status=status):
                self.waitid.return_value = self.status(code=code, status=status)
                self.assertEqual(self.ops.observe_worker(self.handle)['state'], 'UNAVAILABLE')
                self.assert_observation_only()

    def test_unavailable_waitid_or_nowait_never_falls_back_to_consuming_wait(self):
        for name in ('waitid', 'WNOWAIT', 'WEXITED', 'WNOHANG'):
            with self.subTest(name=name):
                with patch.object(supervisor.os, name, None):
                    self.assertEqual(self.ops.observe_worker(self.handle)['state'], 'UNAVAILABLE')
                self.assert_observation_only()
        self.waitid.assert_not_called()

    def test_echild_latches_unsafe_and_never_manufactures_zero_exit(self):
        self.waitid.side_effect = ChildProcessError(errno.ECHILD, 'synthetic competing reaper')
        self.assertEqual(self.ops.observe_worker(self.handle)['state'], 'UNSAFE')
        with self.assertRaises(ChildProcessError):
            self.ops.signal_group(self.handle, 'KILL')
        self.assert_observation_only()

    def test_wrong_pid_latches_unsafe_instead_of_signalling_reported_pid(self):
        self.waitid.return_value = self.status(pid=WORKER_PID + 1)
        observed = self.ops.observe_worker(self.handle)
        self.assertEqual(observed, dict(state='UNSAFE', code='WAITID_WRONG_PID'))
        with self.assertRaises(ChildProcessError):
            self.ops.signal_worker(self.handle, 'KILL')
        self.assert_observation_only()

    def test_unexpected_zero_pid_is_unsafe_not_terminal_or_absence(self):
        self.waitid.return_value = self.status(pid=0)
        self.assertEqual(self.ops.observe_worker(self.handle), dict(state='UNSAFE', code='WAITID_WRONG_PID'))
        self.assert_observation_only()

    def test_cached_reaped_handle_is_unsafe_before_any_waitid(self):
        self.handle.returncode = 0
        self.assertEqual(self.ops.observe_worker(self.handle)['state'], 'UNSAFE')
        self.waitid.assert_not_called()
        self.assert_observation_only()

    def test_changed_pid_or_unretained_object_never_observed_or_signalled(self):
        self.handle.pid = WORKER_PID + 1
        self.assertEqual(self.ops.observe_worker(self.handle)['state'], 'UNSAFE')
        other = SimpleNamespace(pid=WORKER_PID, returncode=None)
        self.assertEqual(self.ops.observe_worker(other)['state'], 'UNSAFE')
        self.waitid.assert_not_called()
        self.assert_observation_only()

    def test_changed_sigchld_policy_is_unsafe_not_a_terminal_observation(self):
        with patch.object(supervisor.signal, 'getsignal', return_value=signal.SIG_IGN):
            self.assertEqual(self.ops.observe_worker(self.handle)['state'], 'UNSAFE')
        self.waitid.assert_not_called()
        self.assert_observation_only()

    def test_waitid_os_error_is_unavailable_with_original_errno_not_terminal(self):
        self.waitid.side_effect = PermissionError(errno.EPERM, 'synthetic waitid denied')
        self.assertEqual(self.ops.observe_worker(self.handle), dict(state='UNAVAILABLE',
            code='WAITID_ERROR', exception='PermissionError', errno=errno.EPERM))
        self.assert_observation_only()

    def test_competing_reaper_during_waitid_invalidates_terminal_return(self):
        def competing(*args):
            self.handle.returncode = 0
            return self.status()
        self.waitid.side_effect = competing
        self.assertEqual(self.ops.observe_worker(self.handle)['state'], 'UNSAFE')
        self.assert_observation_only()

    def test_consuming_reap_latches_before_wait_and_failure_does_not_reset_it(self):
        first = TimeoutError('synthetic bounded final wait')
        def consume(*, timeout):
            self.assertIn(id(self.handle), self.ops._signalling_disabled)
            self.assertEqual(timeout, 1)
            raise first
        self.handle.wait.side_effect = consume
        with self.assertRaises(TimeoutError) as caught:
            self.ops.reap(self.handle, 1)
        self.assertIs(caught.exception, first)
        for method in (self.ops.signal_group, self.ops.signal_worker):
            with self.assertRaises(ChildProcessError):
                method(self.handle, 'KILL')
        self.group.assert_not_called()
        self.single.assert_not_called()
        self.assertEqual(self.handle.wait.call_count, 1)

    def test_permission_error_from_actual_delegated_signal_is_preserved(self):
        first = PermissionError(errno.EPERM, 'synthetic signal denial')
        self.group.side_effect = first
        with self.assertRaises(PermissionError) as caught:
            self.ops.signal_group(self.handle, 'KILL')
        self.assertIs(caught.exception, first)
        self.assertEqual(caught.exception.errno, errno.EPERM)
        self.group.assert_called_once_with(WORKER_PID, signal.SIGKILL)
        self.handle.wait.assert_not_called()


class WorkerWaitEvidenceTests(unittest.TestCase):
    def test_bare_reaped_hint_is_not_actual_wait_return_evidence(self):
        target = SimpleNamespace(pid=CHILD_PID, exit_code=0, wait=Mock(return_value=0))
        observed = worker._ObservedProcess(target, lambda: None)
        self.assertTrue(observed.reaped)
        self.assertIsNone(observed.wait_evidence)
        target.wait.assert_not_called()
        self.assertEqual(observed.wait(timeout=1), 0)
        self.assertEqual(observed.wait_evidence,
                         dict(pid=CHILD_PID, exit_code=0, wait_returned=True))

    def test_wait_exception_or_noninteger_return_cannot_create_wait_evidence(self):
        for value in (TimeoutError('synthetic wait timeout'), True, None):
            with self.subTest(value_type=type(value).__name__):
                target = SimpleNamespace(pid=CHILD_PID, exit_code=0, wait=Mock())
                if isinstance(value, BaseException):
                    target.wait.side_effect = value
                else:
                    target.wait.return_value = value
                observed = worker._ObservedProcess(target, lambda: None)
                with self.assertRaises((TimeoutError, ValueError)):
                    observed.wait(timeout=1)
                self.assertIsNone(observed.wait_evidence)

    def test_changed_child_handle_pid_invalidates_observed_wait_binding(self):
        target = SimpleNamespace(pid=CHILD_PID, wait=Mock(return_value=0))
        observed = worker._ObservedProcess(target, lambda: None)
        observed.wait(timeout=1)
        target.pid += 1
        self.assertIsNone(observed.wait_evidence)
        self.assertEqual(observed.pid, CHILD_PID)
        target.pid = float(CHILD_PID)
        self.assertIsNone(observed.wait_evidence)

    def test_actual_injected_worker_emits_run_bound_concrete_wait_handoff(self):
        fixture = binding_fixtures.Fixture()
        self.addCleanup(fixture.close)
        fixture.process.pid = CHILD_PID
        messages = []
        result = worker.execute_worker(fixture.plan, binding_fixtures.BOUNDS,
            messages.append, process_factory=fixture.process_factory,
            transport_factory=fixture.transport_factory,
            owned_scope_verified=True, cleanup_token=TOKEN, worker_pid=WORKER_PID)
        closure = result['cleanup_handoff']
        self.assertEqual(closure, handoff(fixture.plan))
        self.assertEqual([m['pid'] for m in messages if m['type'] == 'CHILD'], [CHILD_PID])
        self.assertEqual(len(fixture.process.waits), 1)
        self.assertEqual(len([c for c in fixture.calls if c[0] == 'start']), 1)
        worker.validate_cleanup_handoff(fixture.plan, result,
            worker_pid=WORKER_PID, child_pid=CHILD_PID, token=TOKEN)
        self.assertTrue(result['child_reaped'])
        self.assertEqual(result['receipt']['evidence_kind'], 'SYNTHETIC')

    def test_actual_worker_failure_and_success_handoffs_through_terminal_supervisor(self):
        for errors in (b'', b'Error: synthetic late native-shaped error\n'):
            with self.subTest(integrity_failure=bool(errors)):
                fixture = binding_fixtures.Fixture(errors=errors)
                self.addCleanup(fixture.close)
                fixture.process.pid = CHILD_PID
                emitted = []
                done = worker.execute_worker(fixture.plan, binding_fixtures.BOUNDS,
                    emitted.append, process_factory=fixture.process_factory,
                    transport_factory=fixture.transport_factory, owned_scope_verified=True,
                    cleanup_token=TOKEN, worker_pid=WORKER_PID)
                def use_actual(message):
                    message.clear()
                    message.update(type='DONE', **copy.deepcopy(done))
                ops = Operations(fixture.plan, mutate=use_actual, prior_failure=done['first_failure'])
                with patch.object(supervisor.os, 'urandom', return_value=bytes.fromhex(TOKEN)):
                    result = supervisor.supervise(fixture.plan, BOUNDS, ops=ops, clock=ops.clock)
                self.assertTrue(result['terminal_cleanup'])
                self.assertTrue(result['worker_reap_within_deadline'])
                self.assertEqual([v[1] for v in ops.log if v[0] == 'group'], ['TERM'])
                payload = worker.validate_worker_result(fixture.plan, result['worker_result'])
                if errors:
                    self.assertEqual(result['status'], 'COMPLETED_WITH_FAILURE')
                    self.assertEqual(result['first_failure']['worker_failure'], done['first_failure'])
                    self.assertEqual(payload['record']['experiment_status'], 'FAIL')
                else:
                    self.assertEqual(result['status'], 'WORKER_COMPLETED')
                    self.assertEqual(payload['record_kind'], 'RUN')

    def test_missing_child_identity_preserves_completed_failure_without_closure(self):
        fixture = binding_fixtures.Fixture(errors=b'Error: synthetic prior failure\n')
        self.addCleanup(fixture.close)
        done = worker.execute_worker(fixture.plan, binding_fixtures.BOUNDS, lambda _: None,
            process_factory=fixture.process_factory, transport_factory=fixture.transport_factory,
            owned_scope_verified=True, cleanup_token=TOKEN, worker_pid=WORKER_PID)
        self.assertIsNone(done['cleanup_handoff'])
        self.assertIsNotNone(done['first_failure'])
        payload = worker.validate_worker_result(fixture.plan, done)
        self.assertEqual(payload['record']['experiment_status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
