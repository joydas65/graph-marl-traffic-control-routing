"""API-shaped synthetic ownership tests; never acquire a process or socket."""

import unittest

from scripts.b0.od_integration_v1.owned_runtime import (
    OwnedRuntime, OwnedRuntimeCleanupError, RuntimeBounds,
)


BOUNDS = RuntimeBounds(startup=11, connect=7, transport=3, close=2,
                       wait=13, terminate_wait=5, kill_wait=1)


class ProcessDouble:
    def __init__(self, log, waits=(0,), terminate_error=None, kill_error=None):
        self.log = log
        self.waits = iter(waits)
        self.terminate_error = terminate_error
        self.kill_error = kill_error

    def wait(self, *, timeout):
        self.log.append(("wait", timeout))
        value = next(self.waits)
        if isinstance(value, BaseException):
            raise value
        return value

    def terminate(self, *, timeout):
        self.log.append(("terminate", timeout))
        if self.terminate_error is not None:
            raise self.terminate_error

    def kill(self, *, timeout):
        self.log.append(("kill", timeout))
        if self.kill_error is not None:
            raise self.kill_error


class TransportDouble:
    def __init__(self, log, close_error=None, step_error=None):
        self.log = log
        self.close_error = close_error
        self.step_error = step_error
        self.simulation, self.lane, self.vehicle, self.trafficlight = (object() for _ in range(4))

    def simulationStep(self, *args, **kwargs):
        self.log.append(("step", args, kwargs))
        if self.step_error is not None:
            raise self.step_error
        return "synthetic step"

    def close(self, *, timeout):
        self.log.append(("close", timeout))
        if self.close_error is not None:
            raise self.close_error


class OwnershipTests(unittest.TestCase):
    def make_runtime(self, *, waits=(0,), process_error=None, connect_error=None,
                     close_error=None, step_error=None, terminate_error=None, kill_error=None):
        log = []
        process = ProcessDouble(log, waits, terminate_error, kill_error)
        transport = TransportDouble(log, close_error, step_error)
        plan = ("synthetic validated plan",)

        def process_factory(actual_plan, *, timeout):
            log.append(("start", actual_plan, timeout))
            if process_error is not None:
                raise process_error
            return process

        def transport_factory(*, process, plan, timeout, transport_timeout):
            log.append(("connect", process, plan, timeout, transport_timeout))
            if connect_error is not None:
                raise connect_error
            return transport

        runtime = OwnedRuntime(plan, bounds=BOUNDS, process_factory=process_factory,
                               transport_factory=transport_factory)
        return runtime, log, process, transport, plan

    def test_all_bounds_are_required_positive_finite_nonboolean(self):
        for field in BOUNDS.__dataclass_fields__:
            for invalid in (None, True, False, 0, -1, float("inf"), float("nan"), "1", 10**1000):
                with self.subTest(field=field, invalid=repr(invalid)):
                    values = dict(vars(BOUNDS)); values[field] = invalid
                    with self.assertRaises(ValueError):
                        RuntimeBounds(**values)

    def test_no_implicit_factory_or_default_runtime_bound(self):
        for bounds, process_factory, transport_factory in (
            (None, lambda: None, lambda: None), (BOUNDS, None, lambda: None),
            (BOUNDS, lambda: None, None),
        ):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                OwnedRuntime(None, bounds=bounds, process_factory=process_factory,
                             transport_factory=transport_factory)

    def test_start_forwards_exact_plan_and_every_acquisition_bound_once(self):
        runtime, log, process, transport, plan = self.make_runtime()
        self.assertEqual(runtime.state, "NEW")
        self.assertEqual(log, [])
        self.assertIs(runtime.start(), transport)
        self.assertEqual(log, [("start", plan, 11), ("connect", process, plan, 7, 3)])
        self.assertEqual(runtime.state, "CONNECTED")
        with self.assertRaises(RuntimeError):
            runtime.start()
        self.assertEqual(len(log), 2)
        runtime.close()

    def test_api_domains_and_step_are_forwarded_without_manufactured_result(self):
        runtime, log, _, transport, _ = self.make_runtime(); runtime.start()
        for domain in ("simulation", "lane", "vehicle", "trafficlight"):
            with self.subTest(domain=domain):
                self.assertIs(getattr(runtime, domain), getattr(transport, domain))
        self.assertEqual(runtime.simulationStep(1, marker="synthetic"), "synthetic step")
        self.assertEqual(log[-1], ("step", (1,), {"marker": "synthetic"}))
        runtime.close()

    def test_capture_precedes_close_and_process_wait_precedes_output(self):
        runtime, log, _, _, _ = self.make_runtime(); runtime.start()
        log.append(("capture",))
        self.assertIsNone(runtime.close(wait=True))
        log.append(("read_final_output", runtime.finalization_process))
        self.assertEqual(log[2:], [("capture",), ("close", 2), ("wait", 13),
                                  ("read_final_output", {"state": "EXITED", "exit_code": 0})])
        self.assertEqual(runtime.state, "CLOSED")
        self.assertIsNone(runtime.first_failure)

    def test_second_close_is_noop_and_closed_runtime_cannot_restart(self):
        runtime, log, _, _, _ = self.make_runtime(); runtime.start(); runtime.close()
        before = list(log)
        self.assertIsNone(runtime.close())
        with self.assertRaises(RuntimeError):
            runtime.start()
        with self.assertRaises(RuntimeError):
            runtime.simulationStep()
        self.assertEqual(log, before)

    def test_never_started_close_acquires_nothing(self):
        runtime, log, _, _, _ = self.make_runtime(); runtime.close()
        self.assertEqual(log, [])
        self.assertEqual(runtime.finalization_process, {"state": "UNOBSERVED", "exit_code": None})
        with self.assertRaises(RuntimeError):
            runtime.start()

    def test_no_wait_false_escape_hatch(self):
        runtime, log, _, _, _ = self.make_runtime(); runtime.start()
        with self.assertRaises(ValueError):
            runtime.close(wait=False)
        self.assertEqual(len(log), 2)
        self.assertEqual(runtime.state, "CONNECTED")
        runtime.close()

    def test_failed_start_is_one_shot_without_fake_handle_or_fake_wait(self):
        error = TimeoutError("synthetic startup timeout")
        runtime, log, _, _, _ = self.make_runtime(process_error=error)
        with self.assertRaises(TimeoutError) as seen:
            runtime.start()
        self.assertIs(seen.exception, error)
        self.assertEqual([entry[0] for entry in log], ["start"])
        self.assertEqual(runtime.first_failure["operation"], "PROCESS_START")
        self.assertEqual(runtime.first_failure["outcome"], "TIMEOUT")
        self.assertEqual(runtime.finalization_process["state"], "UNOBSERVED")
        with self.assertRaises(RuntimeError):
            runtime.start()

    def test_failed_connect_cleans_owned_process_without_retry_or_fake_close(self):
        error = OSError("synthetic connect failure")
        runtime, log, _, _, _ = self.make_runtime(connect_error=error)
        with self.assertRaises(OSError) as seen:
            runtime.start()
        self.assertIs(seen.exception, error)
        self.assertEqual([entry[0] for entry in log], ["start", "connect", "wait"])
        self.assertEqual(runtime.first_failure["operation"], "TRANSPORT_CONNECT")
        self.assertEqual(runtime.finalization_process, {"state": "EXITED", "exit_code": 0})
        with self.assertRaises(RuntimeError):
            runtime.start()

    def test_failed_connect_retains_later_cleanup_timeout_and_original_failure(self):
        error = ConnectionError("synthetic connection failure")
        runtime, log, _, _, _ = self.make_runtime(connect_error=error, waits=(TimeoutError(), -15))
        with self.assertRaises(ConnectionError) as seen:
            runtime.start()
        self.assertIs(seen.exception, error)
        self.assertEqual(runtime.first_failure["operation"], "TRANSPORT_CONNECT")
        self.assertEqual([entry[0] for entry in log], ["start", "connect", "wait", "terminate", "wait"])
        self.assertEqual(runtime.lifecycle[-3]["outcome"], "TIMEOUT")
        self.assertEqual(runtime.finalization_process["exit_code"], -15)

    def test_connection_loss_is_not_retried_or_reclassified_by_owner(self):
        error = ConnectionError("synthetic lost connection")
        runtime, log, _, _, _ = self.make_runtime(step_error=error); runtime.start()
        with self.assertRaises(ConnectionError) as seen:
            runtime.simulationStep()
        self.assertIs(seen.exception, error)
        runtime.close()
        self.assertEqual([entry[0] for entry in log], ["start", "connect", "step", "close", "wait"])

    def test_close_error_still_waits_and_raises_typed_cleanup_failure(self):
        runtime, log, _, _, _ = self.make_runtime(close_error=OSError()); runtime.start()
        with self.assertRaises(OwnedRuntimeCleanupError):
            runtime.close()
        self.assertEqual(log[-2:], [("close", 2), ("wait", 13)])
        self.assertEqual(runtime.first_failure["operation"], "TRANSPORT_CLOSE")
        self.assertEqual(runtime.finalization_process["state"], "EXITED")

    def test_initial_wait_timeout_terminates_then_retains_timeout_after_exit(self):
        runtime, log, _, _, _ = self.make_runtime(waits=(TimeoutError(), -15)); runtime.start()
        with self.assertRaises(OwnedRuntimeCleanupError):
            runtime.close()
        self.assertEqual(log[2:], [("close", 2), ("wait", 13), ("terminate", 2), ("wait", 5)])
        self.assertEqual(runtime.finalization_process, {"state": "EXITED", "exit_code": -15})
        self.assertEqual(runtime.first_failure["operation"], "PROCESS_WAIT")

    def test_complete_timeout_escalation_stops_after_bounded_kill_wait(self):
        runtime, log, _, _, _ = self.make_runtime(waits=(TimeoutError(), TimeoutError(), TimeoutError()))
        runtime.start()
        with self.assertRaises(OwnedRuntimeCleanupError):
            runtime.close()
        self.assertEqual(log[2:], [("close", 2), ("wait", 13), ("terminate", 2),
                                  ("wait", 5), ("kill", 2), ("wait", 1)])
        self.assertEqual(runtime.finalization_process, {"state": "NOT_EXITED", "exit_code": None})
        self.assertEqual(runtime.state, "CLOSED")

    def test_kill_exit_is_observed_not_assumed_from_successful_kill(self):
        runtime, _, _, _, _ = self.make_runtime(waits=(TimeoutError(), TimeoutError(), -9)); runtime.start()
        with self.assertRaises(OwnedRuntimeCleanupError):
            runtime.close()
        self.assertEqual(runtime.finalization_process, {"state": "EXITED", "exit_code": -9})
        self.assertEqual(runtime.lifecycle[-1]["exit_code"], -9)

    def test_terminate_and_kill_errors_do_not_skip_remaining_waits(self):
        runtime, log, _, _, _ = self.make_runtime(waits=(TimeoutError(), TimeoutError(), TimeoutError()),
                                                terminate_error=OSError(), kill_error=OSError())
        runtime.start()
        with self.assertRaises(OwnedRuntimeCleanupError):
            runtime.close()
        self.assertEqual([entry[0] for entry in log][-6:], ["close", "wait", "terminate", "wait", "kill", "wait"])
        self.assertEqual(sum(event["outcome"] != "COMPLETED" for event in runtime.lifecycle), 5)

    def test_nonzero_natural_exit_is_retained_without_inventing_cleanup_exception(self):
        runtime, log, _, _, _ = self.make_runtime(waits=(4,)); runtime.start(); runtime.close()
        self.assertEqual(runtime.finalization_process, {"state": "EXITED", "exit_code": 4})
        self.assertIsNone(runtime.first_failure)
        self.assertEqual(log[-1], ("wait", 13))

    def test_invalid_exit_values_do_not_establish_exit(self):
        for invalid in (None, True, 0.0, "0"):
            with self.subTest(invalid=invalid):
                runtime, _, _, _, _ = self.make_runtime(waits=(invalid, invalid, invalid)); runtime.start()
                with self.assertRaises(OwnedRuntimeCleanupError):
                    runtime.close()
                self.assertEqual(runtime.finalization_process["state"], "NOT_EXITED")
                self.assertEqual(runtime.first_failure["exception"], "TypeError")

    def test_missing_transport_close_does_not_leak_acquired_process(self):
        runtime, log, _, _, _ = self.make_runtime(); runtime.start()
        runtime._connection = object()
        with self.assertRaises(OwnedRuntimeCleanupError):
            runtime.close()
        self.assertEqual(log[-1], ("wait", 13))
        self.assertEqual(runtime.finalization_process["state"], "EXITED")

    def test_none_factory_return_rejected_without_invented_connection(self):
        runtime = OwnedRuntime(None, bounds=BOUNDS, process_factory=lambda *a, **k: None,
                               transport_factory=lambda **k: self.fail("connect should not occur"))
        with self.assertRaises(TypeError):
            runtime.start()
        self.assertEqual(runtime.finalization_process["state"], "UNOBSERVED")
        self.assertEqual(len(runtime.lifecycle), 1)

    def test_none_transport_return_still_cleans_acquired_process(self):
        log = []; process = ProcessDouble(log)
        runtime = OwnedRuntime(None, bounds=BOUNDS, process_factory=lambda *a, **k: process,
                               transport_factory=lambda **k: None)
        with self.assertRaises(TypeError):
            runtime.start()
        self.assertEqual(log, [("wait", 13)])
        self.assertEqual(runtime.finalization_process["state"], "EXITED")

    def test_close_cancellation_waits_then_reraises_original(self):
        error = KeyboardInterrupt()
        runtime, log, _, _, _ = self.make_runtime(close_error=error); runtime.start()
        with self.assertRaises(KeyboardInterrupt) as seen:
            runtime.close()
        self.assertIs(seen.exception, error)
        self.assertEqual(log[-1], ("wait", 13))
        self.assertEqual(runtime.state, "CLOSED")

    def test_retained_record_copies_cannot_erase_failure_or_exit(self):
        runtime, _, _, _, _ = self.make_runtime(close_error=OSError()); runtime.start()
        with self.assertRaises(OwnedRuntimeCleanupError):
            runtime.close()
        events, failure, process = runtime.lifecycle, runtime.first_failure, runtime.finalization_process
        events.clear(); failure.clear(); process["state"] = "UNOBSERVED"
        self.assertEqual(len(runtime.lifecycle), 4)
        self.assertEqual(runtime.first_failure["operation"], "TRANSPORT_CLOSE")
        self.assertEqual(runtime.finalization_process["state"], "EXITED")

    def test_reentrant_close_cannot_duplicate_owned_cleanup(self):
        runtime, log, _, transport, _ = self.make_runtime(); runtime.start()
        transport.close = lambda **kw: runtime.close()
        with self.assertRaises(OwnedRuntimeCleanupError):
            runtime.close()
        self.assertEqual(log[-1], ("wait", 13))
        self.assertEqual(len(runtime.lifecycle), 4)
        self.assertEqual(runtime.first_failure["exception"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
