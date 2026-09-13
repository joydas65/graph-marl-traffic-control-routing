"""Production supervisor exercised with synthetic IPC/process/clock operations.

No helper, process, signal or socket is created. These cases establish ordering
and deadline arithmetic, not native cancellation or simulator compatibility.
"""

from types import SimpleNamespace
import unittest

from scripts.b0.od_integration_v1.owned_runtime import RuntimeBounds
from scripts.b0.od_integration_v1 import native_supervisor as supervisor


class SyntheticClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class SyntheticOperations:
    """Finite scheduled IPC; all operation ordering remains visible to tests."""

    def __init__(self, clock, messages=(), *, verified=True, bootstrap_elapsed=0,
                 reap_error=None, verify_error=None, signal_error=None,
                 post_handle_error=None, pause_overrun=0, finish_error=None):
        self.clock = clock
        self.messages = list(messages)
        self.verified = verified
        self.bootstrap_elapsed = bootstrap_elapsed
        self.reap_error = reap_error
        self.verify_error = verify_error
        self.signal_error = signal_error
        self.post_handle_error = post_handle_error
        self.pause_overrun = pause_overrun
        self.finish_error = finish_error
        self.handle = SimpleNamespace(pid=49152)
        self.log = []
        self.validation_calls = []
        self.reaped = False
        self.poll_interval = 0.1

    def bootstrap(self, plan, bounds):
        self.log.append(("bootstrap", self.clock()))
        self.clock.advance(self.bootstrap_elapsed)
        if self.post_handle_error is not None:
            self.post_handle_error.worker_handle = self.handle
            raise self.post_handle_error
        return self.handle

    def verify_scope(self, handle):
        if handle is not self.handle:
            raise AssertionError("unowned handle verification")
        self.log.append(("verify_scope", self.clock()))
        if self.verify_error is not None:
            raise self.verify_error
        return self.verified

    def send(self, handle, message, deadline):
        if handle is not self.handle:
            raise AssertionError("unowned handle send")
        self.log.append(("send", message, deadline, self.clock()))
        if self.clock() >= deadline:
            raise TimeoutError("synthetic send deadline")

    def receive(self, handle, deadline):
        if handle is not self.handle:
            raise AssertionError("unowned handle receive")
        self.log.append(("receive", deadline, self.clock()))
        if self.clock() >= deadline:
            raise TimeoutError("synthetic receive deadline")
        if self.messages and self.messages[0][0] <= min(deadline, self.clock() + self.poll_interval):
            at, message = self.messages.pop(0)
            self.clock.now = max(self.clock(), at)
            if isinstance(message, BaseException):
                raise message
            return message
        self.clock.now = min(deadline, self.clock() + self.poll_interval)
        return None

    def signal_group(self, handle, signal):
        if handle is not self.handle or not self.verified or self.reaped:
            raise AssertionError("unsafe process group signal")
        self.log.append(("signal_group", handle.pid, signal, self.clock()))
        if self.signal_error is not None:
            raise self.signal_error

    def signal_worker(self, handle, signal):
        if handle is not self.handle or self.reaped:
            raise AssertionError("unsafe worker signal")
        self.log.append(("signal_worker", handle.pid, signal, self.clock()))
        if self.signal_error is not None:
            raise self.signal_error

    def pause(self, deadline):
        self.log.append(("pause", deadline, self.clock()))
        self.clock.now = max(self.clock(), deadline) + self.pause_overrun

    def reap(self, handle, deadline):
        if handle is not self.handle:
            raise AssertionError("unowned handle reap")
        self.log.append(("reap", deadline, self.clock()))
        if self.reap_error is not None:
            self.clock.now = max(self.clock(), deadline)
            raise self.reap_error
        self.reaped = True
        return 0

    def finish(self, handle):
        if handle is not self.handle:
            raise AssertionError("unowned handle finish")
        self.log.append(("finish", self.clock()))
        if self.finish_error is not None:
            raise self.finish_error

    def validate_result(self, plan, done):
        self.validation_calls.append(done)
        return done


RUNTIME = RuntimeBounds(startup=2, connect=2, transport=1, close=1,
                        wait=1, terminate_wait=1, kill_wait=1)


def make_bounds(**changed):
    values = dict(runtime=RUNTIME, bootstrap=2, total=20, finalize=3, cleanup=4)
    values.update(changed)
    return supervisor.SupervisorBounds(**values)


class SupervisorBoundTests(unittest.TestCase):
    def test_all_supervisor_bounds_are_positive_finite_nonboolean(self):
        for field in ("bootstrap", "total", "finalize", "cleanup"):
            for invalid in (None, True, False, 0, -1, float("inf"), float("nan"), "1", 10**1000):
                with self.subTest(field=field, invalid=repr(invalid)):
                    with self.assertRaises(ValueError):
                        make_bounds(**{field: invalid})

    def test_runtime_bounds_must_be_explicit(self):
        for invalid in (None, {}, 1, "runtime"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                make_bounds(runtime=invalid)


def ready(at=0.1, pid=49152):
    return (at, {"type": "READY", "pid": pid})


def phase(at, name, **extra):
    return (at, {"type": "PHASE", "phase": name, **extra})


def done(at=0.7, child_reaped=True):
    return (at, {"type": "DONE", "child_reaped": child_reaped,
                 "receipt": {"fixture": "synthetic operational result only"}})


def success_messages():
    return [ready(), (0.15, {"type": "CHILD", "pid": 49153}),
            phase(0.2, "CONNECT"), phase(0.3, "RUN"),
            (0.4, {"type": "EXCHANGE_BEGIN", "deadline": 1.4}),
            (0.5, {"type": "EXCHANGE_END"}), phase(0.6, "FINALIZE"), done()]


class SupervisorControlFlowTests(unittest.TestCase):
    def run_supervisor(self, messages=(), *, bounds=None, cancelled=None, **options):
        clock = SyntheticClock()
        ops = SyntheticOperations(clock, messages, **options)
        plan = SimpleNamespace(run_id="synthetic-worker-run", evidence_kind="SYNTHETIC")
        result = supervisor.supervise(plan, bounds or make_bounds(), ops=ops, clock=clock,
            cancelled=(lambda: False) if cancelled is None else lambda: cancelled(clock, ops))
        return result, ops, clock

    def assert_interrupt(self, result):
        self.assertEqual(result["status"], "INTERRUPTED")
        self.assertIsNotNone(result["first_failure"])
        self.assertFalse(result["ready_to_run"])

    def assert_owned_signals_then_reap(self, ops):
        signal_indices = [i for i, x in enumerate(ops.log) if x[0].startswith("signal_")]
        reap_indices = [i for i, x in enumerate(ops.log) if x[0] == "reap"]
        self.assertTrue(signal_indices)
        self.assertEqual(len(reap_indices), 1)
        self.assertLess(max(signal_indices), reap_indices[0])
        self.assertTrue(all(ops.log[i][1] == ops.handle.pid for i in signal_indices))
        self.assertEqual([ops.log[i][2] for i in signal_indices], ["TERM", "KILL"])

    def test_owned_scope_verified_before_single_go_and_no_retry(self):
        result, ops, _ = self.run_supervisor(success_messages())
        self.assertEqual(result["status"], "WORKER_COMPLETED")
        self.assertTrue(result["ownership_verified"])
        self.assertTrue(result["go_sent"])
        self.assertTrue(result["worker_reaped"])
        # Legacy boolean-only DONE is not concrete run-bound child-wait proof.
        self.assertEqual(result["child_scope"], "UNRESOLVED")
        self.assertFalse(result["terminal_cleanup"])
        self.assertNotIn("type", result["worker_result"])
        self.assertEqual(result["worker_result"], {
            "child_reaped": True,
            "receipt": {"fixture": "synthetic operational result only"},
        })
        self.assertEqual(len([x for x in ops.log if x[0] == "bootstrap"]), 1)
        sends = [x for x in ops.log if x[0] == "send"]
        self.assertEqual(len(sends), 1)
        self.assertEqual(sends[0][1]["type"], "GO")
        self.assertLess([x[0] for x in ops.log].index("verify_scope"),
                        [x[0] for x in ops.log].index("send"))
        self.assert_owned_signals_then_reap(ops)

    def test_explicit_initial_bootstrap_limitation_is_retained(self):
        result, _, _ = self.run_supervisor(success_messages())
        self.assertEqual(result["bootstrap_limitation"], "PRE_HANDLE_OS_BOOTSTRAP_NOT_INTERRUPTIBLE")
        self.assertEqual(result["evidence_kind"], "SYNTHETIC")
        self.assertEqual(result["record_kind"], "NATIVE_OPERATIONAL_RECEIPT")

    def test_bootstrap_return_after_deadline_never_authorizes_sumo(self):
        result, ops, _ = self.run_supervisor([ready()], bootstrap_elapsed=3)
        self.assert_interrupt(result)
        self.assertFalse(result["go_sent"])
        self.assertEqual(result["first_failure"]["operation"], "BOOTSTRAP")
        self.assertEqual(result["first_failure"]["code"], "TIMEOUT")
        self.assertFalse(any(x[0] == "send" for x in ops.log))
        self.assert_owned_signals_then_reap(ops)

    def test_unverified_scope_signals_only_owned_worker_not_group(self):
        result, ops, _ = self.run_supervisor([ready()], verified=False)
        self.assert_interrupt(result)
        self.assertFalse(result["go_sent"])
        self.assertFalse(result["ownership_verified"])
        self.assertFalse(any(x[0] == "signal_group" for x in ops.log))
        self.assert_owned_signals_then_reap(ops)

    def test_scope_query_failure_does_not_leak_worker_or_authorize_sumo(self):
        result, ops, _ = self.run_supervisor([ready()], verify_error=ProcessLookupError())
        self.assert_interrupt(result)
        self.assertFalse(result["go_sent"])
        self.assertFalse(any(x[0] == "signal_group" for x in ops.log))
        self.assert_owned_signals_then_reap(ops)

    def test_ready_cannot_supply_unrelated_termination_identity(self):
        result, ops, _ = self.run_supervisor([ready(pid=66666)])
        self.assert_interrupt(result)
        self.assertFalse(result["go_sent"])
        self.assert_owned_signals_then_reap(ops)

    def test_ready_pid_requires_exact_integer(self):
        result, ops, _ = self.run_supervisor([ready(pid=49152.0)])
        self.assert_interrupt(result)
        self.assertFalse(result["go_sent"])
        self.assert_owned_signals_then_reap(ops)

    def test_worker_exit_before_handoff_never_sends_go(self):
        result, ops, _ = self.run_supervisor([(0.1, EOFError())])
        self.assert_interrupt(result)
        self.assertFalse(result["go_sent"])
        self.assertIsNone(result["worker_result"])
        self.assert_owned_signals_then_reap(ops)

    def test_startup_stall_before_child_handle_is_group_cleaned(self):
        result, ops, _ = self.run_supervisor([ready()])
        self.assert_interrupt(result)
        self.assertTrue(result["go_sent"])
        self.assertEqual(result["first_failure"]["operation"], "STARTUP")
        self.assertEqual(result["first_failure"]["code"], "TIMEOUT")
        self.assertEqual(result["child_scope"], "UNRESOLVED")
        self.assert_owned_signals_then_reap(ops)

    def test_connection_or_handshake_stall_has_one_absolute_phase_budget(self):
        result, ops, _ = self.run_supervisor([ready(), phase(0.2, "CONNECT")])
        self.assert_interrupt(result)
        self.assertEqual(result["first_failure"]["operation"], "CONNECT")
        self.assertEqual(result["first_failure"]["code"], "TIMEOUT")
        receives = [x for x in ops.log if x[0] == "receive" and x[2] >= 0.2]
        self.assertTrue(receives)
        self.assertTrue(all(x[1] == 2.2 for x in receives))

    def test_partial_ipc_progress_never_refreshes_startup_deadline(self):
        result, ops, _ = self.run_supervisor([ready()])
        self.assert_interrupt(result)
        receives = [x for x in ops.log if x[0] == "receive" and x[2] >= 0.1]
        self.assertGreater(len(receives), 10)
        self.assertTrue(all(x[1] == 2.1 for x in receives))

    def test_repeated_or_backward_phase_cannot_reset_budget(self):
        for extra in (phase(0.4, "CONNECT"), phase(0.4, "STARTUP"), phase(0.4, "RUN")):
            with self.subTest(phase=extra[1]["phase"]):
                result, ops, _ = self.run_supervisor([ready(), phase(0.2, "CONNECT"), phase(0.3, "RUN"), extra])
                self.assert_interrupt(result)
                self.assertEqual(result["first_failure"]["code"], "ERROR")
                self.assert_owned_signals_then_reap(ops)

    def test_response_stall_retains_complete_exchange_deadline(self):
        result, ops, _ = self.run_supervisor([ready(), phase(0.2, "CONNECT"), phase(0.3, "RUN"),
            (0.4, {"type": "EXCHANGE_BEGIN", "deadline": 0.9})])
        self.assert_interrupt(result)
        self.assertEqual(result["first_failure"]["code"], "TIMEOUT")
        receives = [x for x in ops.log if x[0] == "receive" and x[2] >= 0.4]
        self.assertTrue(receives)
        self.assertTrue(all(x[1] == 0.9 for x in receives))

    def test_message_progress_does_not_reset_exchange_budget_or_first_failure(self):
        first = {"kind": "INTEGRITY", "code": "SYNTHETIC_FIRST"}
        result, ops, _ = self.run_supervisor([ready(), phase(0.2, "CONNECT"), phase(0.3, "RUN"),
            (0.4, {"type": "EXCHANGE_BEGIN", "deadline": 1.0}),
            (0.6, {"type": "FIRST_FAILURE", "failure": first}),
            (0.8, {"type": "FIRST_FAILURE", "failure": {"code": "SYNTHETIC_LATER"}})])
        self.assert_interrupt(result)
        self.assertEqual(result["first_failure"]["worker_failure"], first)
        self.assertTrue(any(x["code"] == "TIMEOUT" for x in result["findings"]))
        receives = [x for x in ops.log if x[0] == "receive" and x[2] >= 0.4]
        self.assertTrue(all(x[1] == 1.0 for x in receives))

    def test_total_budget_is_not_reset_at_finalization(self):
        result, _, _ = self.run_supervisor([ready(), phase(0.2, "CONNECT"), phase(0.3, "RUN"),
            phase(1.0, "FINALIZE"), done(1.2)], bounds=make_bounds(total=1))
        self.assert_interrupt(result)
        self.assertEqual(result["first_failure"]["operation"], "FINALIZE")
        self.assertIsNone(result["worker_result"])

    def test_child_handle_at_expiry_is_ignored_and_never_used_for_signalling(self):
        result, ops, _ = self.run_supervisor([ready(), (2.1, {"type": "CHILD", "pid": 66666})])
        self.assert_interrupt(result)
        self.assertFalse(any(x["code"] == "CHILD_HANDLE_REPORTED" for x in result["findings"]))
        self.assertTrue(any(x["code"] == "LATE_MESSAGE_IGNORED" for x in result["findings"]))
        self.assert_owned_signals_then_reap(ops)

    def test_done_at_finalization_expiry_cannot_restore_success(self):
        result, _, _ = self.run_supervisor([ready(), phase(0.2, "FINALIZE"), done(3.2)])
        self.assert_interrupt(result)
        self.assertFalse(result["normal_finalization"])
        self.assertIsNone(result["worker_result"])

    def test_malformed_late_message_does_not_mask_timeout(self):
        result, _, _ = self.run_supervisor([ready(), (2.1, ["late", "malformed"])])
        self.assert_interrupt(result)
        self.assertEqual(result["first_failure"]["code"], "TIMEOUT")

    def test_finalization_stall_is_interruption_not_fabricated_done(self):
        result, _, _ = self.run_supervisor([ready(), phase(0.2, "FINALIZE")])
        self.assert_interrupt(result)
        self.assertEqual(result["first_failure"]["operation"], "FINALIZE")
        self.assertFalse(result["normal_finalization"])
        self.assertEqual(result["child_scope"], "UNRESOLVED")

    def test_second_child_and_duplicate_ready_do_not_launch_replacement(self):
        for duplicate in ({"type": "CHILD", "pid": 49154}, {"type": "READY", "pid": 49152}):
            with self.subTest(kind=duplicate["type"]):
                result, ops, _ = self.run_supervisor([ready(), (0.15, {"type": "CHILD", "pid": 49153}),
                                                     (0.2, duplicate)])
                self.assert_interrupt(result)
                self.assertEqual(len([x for x in ops.log if x[0] == "bootstrap"]), 1)
                self.assertEqual(len([x for x in ops.log if x[0] == "send"]), 1)

    def test_exchange_begin_end_and_phase_order_are_enforced(self):
        for tail in (
            [(0.4, {"type": "EXCHANGE_END"})],
            [(0.4, {"type": "EXCHANGE_BEGIN", "deadline": 1}),
             (0.5, {"type": "EXCHANGE_BEGIN", "deadline": 2})],
            [(0.4, {"type": "EXCHANGE_BEGIN", "deadline": 1}), phase(0.5, "FINALIZE")],
        ):
            with self.subTest(tail=tail):
                result, _, _ = self.run_supervisor([ready(), phase(0.2, "CONNECT"), phase(0.3, "RUN"), *tail])
                self.assert_interrupt(result)
                self.assertEqual(result["first_failure"]["code"], "ERROR")

    def test_initial_cancel_does_not_even_bootstrap_worker(self):
        result, ops, _ = self.run_supervisor(cancelled=lambda clock, ops: True)
        self.assert_interrupt(result)
        self.assertEqual(ops.log, [])
        self.assertFalse(result["go_sent"])

    def test_cancellation_during_exchange_rejects_later_success(self):
        result, ops, _ = self.run_supervisor(success_messages(), cancelled=lambda clock, ops: clock() >= 0.45)
        self.assert_interrupt(result)
        self.assertEqual(result["first_failure"]["code"], "CANCELLED")
        self.assertIsNone(result["worker_result"])
        self.assert_owned_signals_then_reap(ops)

    def test_cancellation_during_cleanup_cannot_retain_success_status(self):
        result, _, _ = self.run_supervisor(success_messages(), cancelled=lambda clock, ops: clock() >= 1)
        self.assert_interrupt(result)
        self.assertTrue(any(x["code"] == "CANCELLED" for x in result["findings"]))

    def test_worker_reaping_is_not_whole_child_scope_absence(self):
        result, ops, _ = self.run_supervisor([ready()])
        self.assert_interrupt(result)
        self.assertTrue(result["worker_reaped"])
        self.assertEqual(result["child_scope"], "UNRESOLVED")
        self.assert_owned_signals_then_reap(ops)

    def test_done_without_child_reap_proof_keeps_scope_unresolved(self):
        messages = success_messages(); messages[-1] = done(child_reaped=False)
        result, _, _ = self.run_supervisor(messages)
        self.assertEqual(result["status"], "WORKER_COMPLETED")
        self.assertEqual(result["child_scope"], "UNRESOLVED")

    def test_cleanup_reap_timeout_preserves_failure_and_unresolved_scope(self):
        result, ops, _ = self.run_supervisor([ready()], reap_error=TimeoutError())
        self.assert_interrupt(result)
        self.assertFalse(result["worker_reaped"])
        self.assertEqual(result["child_scope"], "UNRESOLVED")
        self.assertEqual(result["first_failure"]["operation"], "STARTUP")
        self.assertTrue(any(x["code"] == "WORKER_REAP_UNRESOLVED" for x in result["findings"]))
        self.assert_owned_signals_then_reap(ops)

    def test_cleanup_signal_failures_are_retained_not_invented_termination(self):
        result, ops, _ = self.run_supervisor([ready()], signal_error=PermissionError())
        self.assert_interrupt(result)
        self.assertEqual(result["child_scope"], "UNRESOLVED")
        self.assertEqual(len([x for x in result["findings"] if x["code"] == "SIGNAL_UNRESOLVED"]), 2)
        self.assert_owned_signals_then_reap(ops)

    def test_cleanup_uses_one_absolute_budget_after_grace(self):
        result, ops, clock = self.run_supervisor([ready()])
        self.assert_interrupt(result)
        term = next(x for x in ops.log if x[0] == "signal_group" and x[2] == "TERM")
        pause = next(x for x in ops.log if x[0] == "pause")
        reap = next(x for x in ops.log if x[0] == "reap")
        self.assertAlmostEqual(reap[1], term[3] + 4)
        self.assertLess(pause[1], reap[1])
        self.assertGreater(reap[1] - reap[2], 0)
        self.assertLessEqual(clock(), reap[1])

    def test_first_failure_and_later_failure_survive_completed_worker(self):
        messages = success_messages()
        messages.insert(5, (0.45, {"type": "FIRST_FAILURE", "failure": {"code": "SYNTHETIC_FIRST"}}))
        messages.insert(7, (0.55, {"type": "FIRST_FAILURE", "failure": {"code": "SYNTHETIC_LATER"}}))
        result, _, _ = self.run_supervisor(messages)
        self.assertEqual(result["status"], "COMPLETED_WITH_FAILURE")
        self.assertEqual(result["first_failure"]["worker_failure"]["code"], "SYNTHETIC_FIRST")
        retained = [x["worker_failure"]["code"] for x in result["findings"] if "worker_failure" in x]
        self.assertEqual(retained, ["SYNTHETIC_FIRST", "SYNTHETIC_LATER"])

    def test_worker_error_and_keyboard_cancellation_do_not_skip_cleanup(self):
        for tail in ((0.2, {"type": "ERROR", "exception": "OSError"}), (0.2, KeyboardInterrupt())):
            with self.subTest(tail=type(tail[1]).__name__):
                result, ops, _ = self.run_supervisor([ready(), tail])
                self.assert_interrupt(result)
                self.assert_owned_signals_then_reap(ops)

    def test_post_bootstrap_handle_setup_error_transfers_cleanup_ownership(self):
        result, ops, _ = self.run_supervisor(post_handle_error=OSError())
        self.assert_interrupt(result)
        self.assertFalse(result["go_sent"])
        self.assertTrue(result["ownership_verified"])
        self.assertTrue(result["worker_reaped"])
        self.assert_owned_signals_then_reap(ops)

    def test_cleanup_budget_overrun_does_not_issue_late_kill_or_fake_reap(self):
        result, ops, _ = self.run_supervisor([ready()], pause_overrun=10)
        self.assert_interrupt(result)
        self.assertFalse(result["worker_reaped"])
        self.assertEqual(result["child_scope"], "UNRESOLVED")
        self.assertEqual([x[2] for x in ops.log if x[0] == "signal_group"], ["TERM"])
        self.assertFalse(any(x[0] == "reap" for x in ops.log))
        self.assertTrue(any(x["code"] == "SIGNAL_UNRESOLVED" for x in result["findings"]))
        self.assertTrue(any(x["code"] == "WORKER_REAP_UNRESOLVED" for x in result["findings"]))

    def test_finish_error_is_retained_after_reaping_without_further_signal(self):
        result, ops, _ = self.run_supervisor([ready()], finish_error=OSError())
        self.assert_interrupt(result)
        self.assertTrue(result["worker_reaped"])
        self.assertTrue(any(x["code"] == "IPC_CLOSE_UNRESOLVED" for x in result["findings"]))
        self.assert_owned_signals_then_reap(ops)


if __name__ == "__main__":
    unittest.main()
