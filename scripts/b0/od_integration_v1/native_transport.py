"""Dormant, worker-local SUMO 1.27.1 transport with whole-exchange deadlines.

Only ``connect_native`` acquires a client/socket. Its native default belongs in
the one-shot owned worker, never in the research/supervisor process. Importing
this module only imports the standard library. Offline tests inject a loader
and raw sockets; they do not import or execute the installed client.

The official v1_27_1 ``tools/traci/connection.py`` sends once and receives a
length-prefixed response in a loop. A private socket facade completes partial
sends and applies the *same absolute deadline* to every connect/send/recv. The
supervisor independently observes BEGIN/END and enforces expiry if Python,
native code, a callback, or the operating system does not return. Socket
timeouts alone are not an ownership or hard real-time guarantee.
"""

from contextlib import contextmanager
import hashlib
import importlib
import importlib.util
import itertools
import math
from pathlib import Path
import sys
import time


VERSION = "1.27.1"
PROTOCOL = 22
CLIENT_SHA256 = {
    "constants.py": "42fa43f203bac2194b0758e8a7fba50873d3d4043648ab69cc58dc62a29e66dc",
    "connection.py": "05820ab615a2ab18411e9722ebbc7056856f2de155383a8b58120d2b2feac572",
    "_simulation.py": "8b7f97ced4dd6774271e8e0da270d687aa9a5ff438c8090023a941beb4e8bbec",
    "_trafficlight.py": "4757c6336d7edf37a7d1473d050731e40a18e4a4d9220babb564af2abaaac4c9",
    "_lane.py": "1b785163f695807cb8ea129cba9c42f243f3974a4a0d3d49ed442f362f043e6a",
    "_vehicle.py": "4c6bcdad2628f044ce235188f0269d6a5bcaf47e7836396d363280ecb91f0328",
}
_NAMES = itertools.count()


def _positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("FINITE_POSITIVE_TRANSPORT_BOUND_REQUIRED")
    try:
        valid = math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("FINITE_POSITIVE_TRANSPORT_BOUND_REQUIRED")
    return value


class _Deadline:
    """Single-threaded, nested operations share their outer absolute budget."""

    def __init__(self, clock, callback):
        self.clock = clock
        self.callback = callback
        self.active = None
        self.callback_failures = []
        self.last_now = None

    def now(self):
        value = self.clock()
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("MONOTONIC_CLOCK_VALUE")
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("MONOTONIC_CLOCK_VALUE")
        if self.last_now is not None and value < self.last_now:
            raise ValueError("MONOTONIC_CLOCK_MOVED_BACKWARDS")
        self.last_now = value
        return value

    def remaining(self):
        if self.active is None:
            raise RuntimeError("SOCKET_OPERATION_WITHOUT_EXCHANGE_DEADLINE")
        remaining = self.active - self.now()
        if remaining <= 0:
            raise TimeoutError("NATIVE_EXCHANGE_DEADLINE_EXPIRED")
        return remaining

    @contextmanager
    def budget(self, seconds):
        _positive(seconds)
        if self.active is not None:
            self.remaining()
            yield self.active
            self.remaining()
            return
        deadline = self.now() + seconds
        if not math.isfinite(deadline):
            raise ValueError("FINITE_ABSOLUTE_DEADLINE_REQUIRED")
        self.active = deadline
        try:
            try:
                if self.callback is not None:
                    self.callback("BEGIN", deadline)
                self.remaining()
                yield deadline
                self.remaining()
            except BaseException:
                # An IPC failure while reporting END must not replace the
                # original native exception (including fatal TraCI errors).
                if self.callback is not None:
                    try:
                        self.callback("END", deadline)
                    except BaseException as error:
                        self.callback_failures.append(error)
                raise
            else:
                if self.callback is not None:
                    self.callback("END", deadline)
        finally:
            self.active = None


class _DeadlineSocket:
    def __init__(self, raw, deadline):
        self.raw = raw
        self.deadline = deadline
        self.closed = False
        self.connected = False

    def _call(self, operation, *args):
        self.raw.settimeout(self.deadline.remaining())
        result = operation(*args)
        self.deadline.remaining()  # Never accept a late successful return.
        return result

    def connect(self, address):
        result = self._call(self.raw.connect, address)
        self.connected = True
        return result

    def send(self, data, flags=0):
        """Native ``send`` becomes complete-send, without renewing its budget."""
        view = memoryview(data)
        sent = 0
        while sent < len(view):
            args = (view[sent:],) if flags == 0 else (view[sent:], flags)
            count = self._call(self.raw.send, *args)
            if type(count) is not int or count < 0 or count > len(view) - sent:
                raise ValueError("INVALID_SOCKET_SEND_RESULT")
            if count == 0:
                raise ConnectionError("SOCKET_CLOSED_DURING_SEND")
            sent += count
        return sent

    def sendall(self, data, flags=0):
        self.send(data, flags)

    def recv(self, size, flags=0):
        args = (size,) if flags == 0 else (size, flags)
        return self._call(self.raw.recv, *args)

    def setsockopt(self, *args):
        self.deadline.remaining()
        result = self.raw.setsockopt(*args)
        self.deadline.remaining()
        return result

    def settimeout(self, requested):
        # Do not permit a client-side request to remove/extend this deadline.
        remaining = self.deadline.remaining()
        if requested is None:
            requested = remaining
        else:
            _positive(requested)
        self.raw.settimeout(min(requested, remaining))

    def close(self):
        # Closing a local descriptor is attempted even after expiry. The
        # independent owned-worker cleanup bounds a close that does not return.
        if not self.closed:
            self.raw.close()
            self.closed = True


class _SocketFacade:
    """Replace only the privately loaded connection module's socket binding."""

    def __init__(self, original, factory, deadline):
        self.original = original
        self.factory = factory
        self.deadline = deadline
        self.created = []
        self.cleanup_failures = []

    def __getattr__(self, name):
        return getattr(self.original, name)

    def socket(self, *args, **kwargs):
        self.deadline.remaining()
        raw = self.factory(*args, **kwargs)
        wrapped = _DeadlineSocket(raw, self.deadline)
        self.created.append(wrapped)  # Retain ownership before the late check.
        self.deadline.remaining()
        return wrapped

    def cleanup(self, *, preserve_exception):
        first = None
        for wrapped in self.created:
            try:
                wrapped.close()
            except BaseException as error:
                self.cleanup_failures.append(error)
                if first is None:
                    first = error
        if first is not None and not preserve_exception:
            raise first


def _load_client(plan):
    """Native-only import from the pinned installation, in a fresh -B worker.

    This deliberately does not execute traci.__init__/main, which can select
    another backend or change sys.path. Native sumolib is an actual dependency
    of TrafficLightDomain (Phase); import its exact sibling package normally,
    refusing any existing canonical sumolib registration. No existing module,
    socket implementation, or installed source is modified. The six reviewed
    client sources are pinned; their installed helper dependency closure is
    location-bound, not represented as fully hash-pinned.
    """
    if not sys.dont_write_bytecode:
        raise ValueError("NATIVE_WORKER_REQUIRES_BYTECODE_DISABLED")
    if dict(plan.client_sha256) != CLIENT_SHA256:
        raise ValueError("PINNED_CLIENT_IDENTITY_MISMATCH")
    client = Path(plan.client_directory)
    if not client.is_absolute() or client.name != "traci":
        raise ValueError("PINNED_CLIENT_DIRECTORY_REQUIRED")
    client = client.resolve(strict=True)
    for name, expected in CLIENT_SHA256.items():
        source = client / name
        if source.is_symlink() or not source.is_file():
            raise ValueError("PINNED_CLIENT_SOURCE_OBJECT")
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError("PINNED_CLIENT_SOURCE_CHANGED")
    if any(name == "sumolib" or name.startswith("sumolib.") for name in sys.modules):
        raise ValueError("NATIVE_WORKER_SUMOLIB_ALREADY_LOADED")
    sumolib = client.parent / "sumolib" / "__init__.py"
    if not sumolib.is_file() or sumolib.is_symlink():
        raise ValueError("NATIVE_SUMOLIB_DEPENDENCY_MISSING")
    spec = importlib.util.spec_from_file_location("sumolib", sumolib,
        submodule_search_locations=[str(sumolib.parent)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["sumolib"] = module
    spec.loader.exec_module(module)

    name = "_b0_owned_traci_" + str(next(_NAMES))
    if name in sys.modules:
        raise RuntimeError("PRIVATE_CLIENT_NAMESPACE_COLLISION")
    spec = importlib.util.spec_from_file_location(name, client / "__init__.py",
        submodule_search_locations=[str(client)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package  # Do not execute the public package initializer.
    connection = importlib.import_module(name + ".connection")
    constants = importlib.import_module(name + ".constants")
    if constants.TRACI_VERSION != PROTOCOL:
        raise ValueError("PINNED_CLIENT_PROTOCOL_MISMATCH")
    for module_name, class_name in (("_simulation", "SimulationDomain"),
            ("_lane", "LaneDomain"), ("_vehicle", "VehicleDomain"),
            ("_trafficlight", "TrafficLightDomain")):
        domain = importlib.import_module(name + "." + module_name)
        getattr(domain, class_name)()
    return connection


def connect_native(process, plan, timeout, transport_timeout, *, clock=time.monotonic,
                   socket_factory=None, loader=None, on_exchange=None, sleeper=time.sleep):
    """Acquire the genuine API, or an explicitly injected offline double.

    ``on_exchange(kind, absolute_deadline)`` receives paired BEGIN/END events.
    Acquisition (including native loading, TCP connect, and getVersion) uses
    one budget. A command's nested send/receive and parsing do not renew it.
    Later exchanges and close each use their own configured outer budget.
    The parent independently enforces total execution and cancellation.

    The returned object exposes native domains/getVersion/simulationStep and
    ``close(timeout=...)``. It never waits for the child; the owner does that.
    A loopback destination is not proof of the server's listening scope.
    Only pre-handshake ConnectionRefusedError can retry, with a new socket and
    a bounded sleep under the original acquisition deadline. There is no
    process relaunch and no retry after any successful TCP connection.
    """
    _positive(timeout)
    _positive(transport_timeout)
    if type(plan.port) is not int or not 1024 <= plan.port <= 65535:
        raise ValueError("EXPLICIT_UNPRIVILEGED_PORT_REQUIRED")
    if on_exchange is not None and not callable(on_exchange):
        raise ValueError("EXCHANGE_CALLBACK_REQUIRED")
    deadline = _Deadline(clock, on_exchange)
    facade = None
    try:
        with deadline.budget(timeout):
            module = (_load_client if loader is None else loader)(plan)
            deadline.remaining()
            original_socket = module.socket
            facade = _SocketFacade(original_socket,
                original_socket.socket if socket_factory is None else socket_factory, deadline)
            module.socket = facade

            class BoundedConnection(module.Connection):
                def _sendExact(self):
                    with deadline.budget(transport_timeout):
                        return super()._sendExact()

                def _sendCmd(self, *args, **kwargs):
                    with deadline.budget(transport_timeout):
                        return super()._sendCmd(*args, **kwargs)

                def getVersion(self):
                    with deadline.budget(transport_timeout):
                        return super().getVersion()

                def simulationStep(self, *args, **kwargs):
                    with deadline.budget(transport_timeout):
                        return super().simulationStep(*args, **kwargs)

                def close(self, *, timeout):
                    _positive(timeout)
                    if getattr(self, "_bounded_closed", False):
                        return
                    self._bounded_closed = True
                    with deadline.budget(timeout):
                        try:
                            super().close(wait=False)
                        except BaseException:
                            facade.cleanup(preserve_exception=True)
                            raise
                        else:
                            facade.cleanup(preserve_exception=False)

            while True:
                try:
                    connection = BoundedConnection("127.0.0.1", plan.port, process,
                                                   traceFile=None, traceGetters=False)
                    break
                except ConnectionRefusedError:
                    facade.cleanup(preserve_exception=True)
                    if facade.cleanup_failures or any(sock.connected for sock in facade.created):
                        raise
                    sleeper(min(0.05, deadline.remaining()))
                    deadline.remaining()
            connection.transport_cleanup_failures = facade.cleanup_failures
            connection.transport_callback_failures = deadline.callback_failures
            version = connection.getVersion()
            if (type(version) is not tuple or len(version) != 2
                    or type(version[0]) is not int or version != (PROTOCOL, "SUMO " + VERSION)):
                raise ValueError("PINNED_NATIVE_VERSION_MISMATCH")
            return connection
    except BaseException:
        if facade is not None:
            facade.cleanup(preserve_exception=True)
        raise
