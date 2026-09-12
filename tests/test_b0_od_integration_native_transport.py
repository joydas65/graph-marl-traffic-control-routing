"""Exercise production deadline calls with API-shaped doubles, never native IO."""

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from scripts.b0.od_integration_v1 import native_transport as transport


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class RawSocket:
    def __init__(self, clock, log):
        self.clock, self.log = clock, log
        self.actions = {name: [] for name in ("connect", "send", "recv", "close")}
        self.timeout = None
        self.closed = False

    def settimeout(self, timeout):
        self.timeout = timeout
        self.log.append(("settimeout", timeout))

    def setsockopt(self, *args):
        self.log.append(("setsockopt", args))

    def perform(self, name, args, default):
        self.log.append((name, args, self.timeout))
        advance, result = self.actions[name].pop(0) if self.actions[name] else (0, default)
        self.clock.value += advance
        if isinstance(result, BaseException):
            raise result
        return result

    def connect(self, address):
        return self.perform("connect", address, None)

    def send(self, data, *flags):
        return self.perform("send", (bytes(data), flags), len(data))

    def recv(self, size, *flags):
        return self.perform("recv", (size, flags), b"x" * size)

    def close(self):
        self.perform("close", (), None)
        self.closed = True


class NativeError(Exception):
    """A fatal native-client-shaped exception, not an OSError."""


class Fixture:
    def __init__(self):
        self.clock, self.log, self.events = Clock(), [], []
        self.raw = RawSocket(self.clock, self.log)
        self.raw_queue = [self.raw]
        self.plan = SimpleNamespace(port=8873, client_directory="synthetic-client",
                                    client_sha256={})
        self.process = SimpleNamespace(wait=self.forbidden_wait)
        self.state = SimpleNamespace(version=(22, "SUMO 1.27.1"),
            after_connect_error=None, exchange_error=None, close_error=None)
        self.original_socket = SimpleNamespace(IPPROTO_TCP=6, TCP_NODELAY=1,
            error=OSError, socket=self.socket_factory)
        self.module = SimpleNamespace(socket=self.original_socket)
        fixture = self

        class ConnectionDouble:
            def __init__(self, host, port, process, traceFile, traceGetters):
                fixture.log.append(("constructor", host, port, process, traceFile, traceGetters))
                self._socket = fixture.module.socket.socket()
                self._socket.setsockopt(fixture.module.socket.IPPROTO_TCP,
                                        fixture.module.socket.TCP_NODELAY, 1)
                try:
                    self._socket.connect((host, port))
                except fixture.module.socket.error:
                    self._socket.close()
                    raise
                if fixture.state.after_connect_error is not None:
                    raise fixture.state.after_connect_error
                self._process = process
                self.simulation, self.lane, self.vehicle, self.trafficlight = (
                    SimpleNamespace() for _ in range(4))

            def _sendCmd(self, *args, **kwargs):
                fixture.log.append(("command", args, kwargs))
                return self._sendExact()

            def _sendExact(self):
                if fixture.state.exchange_error is not None:
                    raise fixture.state.exchange_error
                self._socket.send(b"COMMAND")
                result = b""
                while len(result) < 4:
                    part = self._socket.recv(4 - len(result))
                    if not part:
                        raise NativeError("synthetic EOF")
                    result += part
                return result

            def getVersion(self):
                self._sendCmd("version")
                return fixture.state.version

            def simulationStep(self, *args, **kwargs):
                self._sendCmd("step", *args, **kwargs)
                return "synthetic native-shaped step"

            def close(self, wait=True):
                fixture.log.append(("native_close", wait))
                if fixture.state.close_error is not None:
                    raise fixture.state.close_error
                self._sendCmd("close")
                self._socket.close()
                self._socket = None
                if wait:
                    self._process.wait()

        self.module.Connection = ConnectionDouble

    def forbidden_wait(self):
        raise AssertionError("native close must never wait for the process")

    def socket_factory(self, *args, **kwargs):
        self.log.append(("socket", args, kwargs))
        return self.raw_queue.pop(0)

    def loader(self, plan):
        self.log.append(("loader", plan))
        return self.module

    def callback(self, kind, deadline):
        self.events.append((kind, deadline))

    def connect(self, **kwargs):
        parameters = dict(clock=self.clock, loader=self.loader,
            socket_factory=self.socket_factory, on_exchange=self.callback,
            sleeper=self.clock.sleep)
        parameters.update(kwargs)
        return transport.connect_native(self.process, self.plan, 11, 3, **parameters)


class NativeTransportTests(unittest.TestCase):
    def test_actual_socket_calls_receive_decreasing_remaining_acquisition_budget(self):
        f = Fixture()
        f.raw.actions["connect"] = [(2, None)]
        f.raw.actions["send"] = [(1, 7)]
        f.raw.actions["recv"] = [(1, b"done")]
        api = f.connect()
        self.assertEqual([item[1] for item in f.log if item[0] == "settimeout"], [11, 9, 8])
        self.assertEqual(f.events, [("BEGIN", 111), ("END", 111)])
        constructor = next(item for item in f.log if item[0] == "constructor")
        self.assertEqual(constructor[1:3], ("127.0.0.1", 8873))
        self.assertIs(constructor[3], f.process)
        self.assertEqual(constructor[4:], (None, False))
        for domain in ("simulation", "lane", "vehicle", "trafficlight"):
            with self.subTest(domain=domain):
                self.assertIsNotNone(getattr(api, domain))
        self.assertIs(f.original_socket.socket.__self__, f)
        self.assertIsNot(f.module.socket, f.original_socket)

    def test_nested_native_methods_emit_only_one_pair_per_complete_exchange(self):
        f = Fixture(); api = f.connect(); f.events.clear()
        self.assertEqual(api.simulationStep(1.0, marker="synthetic"), "synthetic native-shaped step")
        self.assertEqual(f.events, [("BEGIN", 103), ("END", 103)])
        f.clock.value = 101
        self.assertEqual(api.getVersion(), (22, "SUMO 1.27.1"))
        self.assertEqual(f.events[-2:], [("BEGIN", 104), ("END", 104)])

    def test_direct_send_exact_also_has_a_complete_exchange_deadline(self):
        f = Fixture(); api = f.connect(); f.events.clear()
        self.assertEqual(api._sendExact(), b"xxxx")
        self.assertEqual(f.events, [("BEGIN", 103), ("END", 103)])

    def test_partial_sends_are_completed_without_resetting_budget(self):
        f = Fixture(); api = f.connect(); f.log.clear(); f.events.clear()
        f.raw.actions["send"] = [(0.5, 2), (0.5, 3), (0.5, 2)]
        api.simulationStep()
        sends = [item for item in f.log if item[0] == "send"]
        self.assertEqual([item[1][0] for item in sends], [b"COMMAND", b"MMAND", b"ND"])
        self.assertEqual([item[2] for item in sends], [3, 2.5, 2])
        self.assertEqual(f.events, [("BEGIN", 103), ("END", 103)])

    def test_continuing_partial_receives_cannot_renew_deadline(self):
        f = Fixture(); api = f.connect(); f.log.clear(); f.events.clear()
        f.raw.actions["recv"] = [(0.9, b"a")] * 4
        with self.assertRaises(TimeoutError):
            api.simulationStep()
        timeouts = [item[2] for item in f.log if item[0] == "recv"]
        for actual, expected in zip(timeouts, [3, 2.1, 1.2, 0.3]):
            with self.subTest(expected=expected):
                self.assertAlmostEqual(actual, expected)
        self.assertEqual(len(timeouts), 4)
        self.assertEqual(f.events, [("BEGIN", 103), ("END", 103)])

    def test_partial_send_stall_is_not_a_fresh_timeout_per_chunk(self):
        f = Fixture(); api = f.connect(); f.log.clear()
        f.raw.actions["send"] = [(1.1, 1)] * 7
        with self.assertRaises(TimeoutError):
            api.simulationStep()
        self.assertEqual(len([item for item in f.log if item[0] == "send"]), 3)
        self.assertFalse(any(item[0] == "recv" for item in f.log))

    def test_raw_timeout_and_non_os_native_errors_keep_their_exact_identity(self):
        for error in (TimeoutError("synthetic stalled recv"), ConnectionError("synthetic lost socket"),
                      NativeError("synthetic native fatal"), ValueError("synthetic protocol defect")):
            with self.subTest(kind=type(error).__name__):
                f = Fixture(); api = f.connect()
                f.raw.actions["recv"] = [(0, error)]
                with self.assertRaises(type(error)) as seen:
                    api.simulationStep()
                self.assertIs(seen.exception, error)

    def test_loader_stall_is_inside_connection_budget_before_any_socket(self):
        f = Fixture()
        def slow_loader(plan):
            f.clock.value += 12
            return f.module
        with self.assertRaises(TimeoutError):
            f.connect(loader=slow_loader)
        self.assertFalse(any(item[0] == "socket" for item in f.log))
        self.assertEqual(f.events, [("BEGIN", 111), ("END", 111)])

    def test_socket_handle_arriving_late_is_retained_and_closed(self):
        f = Fixture()
        def slow_factory():
            f.clock.value += 12
            return f.raw
        with self.assertRaises(TimeoutError):
            f.connect(socket_factory=slow_factory)
        self.assertTrue(f.raw.closed)
        self.assertFalse(any(item[0] == "connect" for item in f.log))

    def test_late_connect_cannot_proceed_to_handshake(self):
        f = Fixture(); f.raw.actions["connect"] = [(12, None)]
        with self.assertRaises(TimeoutError):
            f.connect()
        self.assertTrue(f.raw.closed)
        self.assertFalse(any(item[0] == "send" for item in f.log))

    def test_handshake_uses_connect_budget_remainder_and_rejects_late_result(self):
        f = Fixture()
        f.raw.actions["connect"] = [(8, None)]
        f.raw.actions["recv"] = [(4, b"done")]
        with self.assertRaises(TimeoutError):
            f.connect()
        self.assertTrue(f.raw.closed)
        self.assertEqual([item[2] for item in f.log if item[0] == "recv"], [3])
        self.assertEqual(len([item for item in f.log if item[0] == "socket"]), 1)

    def test_version_mismatch_closes_socket_and_is_not_operational_oserror(self):
        for version in ((22, "SUMO 1.26.0"), (21, "SUMO 1.27.1"), [22, "SUMO 1.27.1"],
                        (22.0, "SUMO 1.27.1")):
            with self.subTest(version=version):
                f = Fixture(); f.state.version = version
                with self.assertRaisesRegex(ValueError, "PINNED_NATIVE_VERSION_MISMATCH"):
                    f.connect()
                self.assertTrue(f.raw.closed)

    def test_refused_connection_can_retry_only_under_original_connect_budget(self):
        f = Fixture()
        second = RawSocket(f.clock, f.log)
        f.raw_queue.append(second)
        f.raw.actions["connect"] = [(2, ConnectionRefusedError("synthetic not listening yet"))]
        f.connect()
        self.assertTrue(f.raw.closed)
        self.assertFalse(second.closed)
        connects = [item for item in f.log if item[0] == "connect"]
        self.assertEqual(len(connects), 2)
        self.assertAlmostEqual(connects[1][2], 8.95)
        self.assertEqual(f.events, [("BEGIN", 111), ("END", 111)])

    def test_repeated_refusal_and_sleep_never_extend_acquisition_budget(self):
        f = Fixture()
        def factory():
            raw = RawSocket(f.clock, f.log)
            raw.actions["connect"] = [(3, ConnectionRefusedError("synthetic refusal"))]
            return raw
        with self.assertRaises(TimeoutError):
            f.connect(socket_factory=factory)
        self.assertEqual(len([item for item in f.log if item[0] == "connect"]), 4)
        self.assertEqual(f.events, [("BEGIN", 111), ("END", 111)])

    def test_refusal_after_tcp_success_does_not_retry_constructor(self):
        f = Fixture(); error = ConnectionRefusedError("synthetic post-connect constructor error")
        f.state.after_connect_error = error
        with self.assertRaises(ConnectionRefusedError) as seen:
            f.connect()
        self.assertIs(seen.exception, error)
        self.assertEqual(len([item for item in f.log if item[0] == "socket"]), 1)
        self.assertTrue(f.raw.closed)

    def test_handshake_refusal_is_not_retried(self):
        f = Fixture(); error = ConnectionRefusedError("synthetic handshake failure")
        f.raw.actions["recv"] = [(0, error)]
        with self.assertRaises(ConnectionRefusedError) as seen:
            f.connect()
        self.assertIs(seen.exception, error)
        self.assertEqual(len([item for item in f.log if item[0] == "socket"]), 1)

    def test_refusal_sleep_that_returns_late_does_not_acquire_replacement_socket(self):
        f = Fixture(); f.raw.actions["connect"] = [(0, ConnectionRefusedError())]
        def late_sleep(seconds):
            self.assertLessEqual(seconds, 11)
            f.clock.value += 12
        with self.assertRaises(TimeoutError):
            f.connect(sleeper=late_sleep)
        self.assertEqual(len([item for item in f.log if item[0] == "socket"]), 1)

    def test_close_has_one_bound_and_disables_native_process_wait(self):
        f = Fixture(); api = f.connect(); f.log.clear(); f.events.clear()
        api.close(timeout=2)
        self.assertIn(("native_close", False), f.log)
        self.assertTrue(f.raw.closed)
        self.assertEqual(f.events, [("BEGIN", 102), ("END", 102)])
        before = list(f.log)
        api.close(timeout=2)
        self.assertEqual(before, f.log)

    def test_failed_orderly_close_still_closes_raw_socket_and_retains_native_error(self):
        f = Fixture(); api = f.connect(); error = NativeError("synthetic close error")
        f.state.close_error = error
        with self.assertRaises(NativeError) as seen:
            api.close(timeout=2)
        self.assertIs(seen.exception, error)
        self.assertTrue(f.raw.closed)

    def test_late_close_response_is_rejected_and_socket_cleanup_attempted(self):
        f = Fixture(); api = f.connect(); f.events.clear()
        f.raw.actions["recv"] = [(3, b"done")]
        with self.assertRaises(TimeoutError):
            api.close(timeout=2)
        self.assertTrue(f.raw.closed)
        self.assertEqual(f.events, [("BEGIN", 102), ("END", 102)])

    def test_socket_close_stall_is_within_reported_close_budget(self):
        f = Fixture(); api = f.connect(); f.events.clear()
        f.raw.actions["close"] = [(3, None)]
        with self.assertRaises(TimeoutError):
            api.close(timeout=2)
        self.assertEqual(f.events, [("BEGIN", 102), ("END", 102)])

    def test_cleanup_failure_does_not_mask_original_close_failure(self):
        f = Fixture(); api = f.connect()
        first, cleanup = NativeError("synthetic first"), OSError("synthetic descriptor cleanup")
        f.state.close_error = first
        f.raw.actions["close"] = [(0, cleanup)]
        with self.assertRaises(NativeError) as seen:
            api.close(timeout=2)
        self.assertIs(seen.exception, first)
        self.assertEqual(api.transport_cleanup_failures, [cleanup])
        self.assertFalse(f.raw.closed)

    def test_end_callback_failure_does_not_mask_original_exchange_failure(self):
        first, callback = NativeError("synthetic first"), OSError("synthetic IPC end")
        f = Fixture()
        enabled = [False]
        def selected(kind, deadline):
            f.callback(kind, deadline)
            if enabled[0] and kind == "END":
                raise callback
        api = f.connect(on_exchange=selected); enabled[0] = True
        f.raw.actions["recv"] = [(0, first)]
        with self.assertRaises(NativeError) as seen:
            api.simulationStep()
        self.assertIs(seen.exception, first)
        self.assertEqual(api.transport_callback_failures, [callback])

    def test_end_callback_failure_on_success_is_not_silently_ignored(self):
        f = Fixture(); error = OSError("synthetic IPC end")
        def callback(kind, deadline):
            if kind == "END":
                raise error
        with self.assertRaises(OSError) as seen:
            f.connect(on_exchange=callback)
        self.assertIs(seen.exception, error)
        self.assertTrue(f.raw.closed)

    def test_invalid_send_results_fail_without_claiming_success(self):
        for count in (0, -1, 8, True, None):
            with self.subTest(count=count):
                f = Fixture(); api = f.connect(); f.raw.actions["send"] = [(0, count)]
                with self.assertRaises((ConnectionError, ValueError)):
                    api.simulationStep()

    def test_eof_remains_a_native_fatal_exception(self):
        f = Fixture(); api = f.connect(); f.raw.actions["recv"] = [(0, b"")]
        with self.assertRaises(NativeError):
            api.simulationStep()

    def test_invalid_bounds_and_ports_fail_before_loader_or_socket(self):
        for key in ("timeout", "transport_timeout"):
            for value in (0, -1, True, None, "3", float("inf"), float("nan"), 10**1000):
                with self.subTest(key=key, value=repr(value)):
                    f = Fixture(); args = dict(timeout=11, transport_timeout=3); args[key] = value
                    with self.assertRaises(ValueError):
                        transport.connect_native(f.process, f.plan, **args, loader=f.loader)
                    self.assertEqual(f.log, [])
        for port in (True, None, 0, 1023, 65536, "8873"):
            with self.subTest(port=port):
                f = Fixture(); f.plan.port = port
                with self.assertRaises(ValueError):
                    f.connect()
                self.assertEqual(f.log, [])

    def test_clock_moving_backwards_is_rejected(self):
        f = Fixture(); api = f.connect(); f.clock.value = 99
        with self.assertRaisesRegex(ValueError, "MONOTONIC_CLOCK_MOVED_BACKWARDS"):
            api.simulationStep()

    def test_default_loader_rejects_unpinned_metadata_before_native_import(self):
        f = Fixture()
        with self.assertRaisesRegex(ValueError, "PINNED_CLIENT_IDENTITY_MISMATCH"):
            transport._load_client(f.plan)

    def test_default_loader_rechecks_source_bytes_before_native_import(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Path(directory) / "traci"; client.mkdir()
            (client / "constants.py").write_text("# small synthetic altered source\n")
            plan = SimpleNamespace(client_directory=str(client), client_sha256=transport.CLIENT_SHA256)
            with self.assertRaisesRegex(ValueError, "PINNED_CLIENT_SOURCE_CHANGED"):
                transport._load_client(plan)


if __name__ == "__main__":
    unittest.main()
