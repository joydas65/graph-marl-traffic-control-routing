"""One-shot ownership of injected process/transport adapters, never a launcher.

No native client is imported and no default factory starts a process or socket.
Every potentially blocking adapter operation receives a finite timeout. This is
a protocol obligation, not a wall-clock guarantee for arbitrary Python doubles:
the native adapter must enforce the supplied deadline in its actual IO/waits.

Factories must clean resources they acquire and do not return. In particular,
an exception before a process/connection handle is returned cannot be cleaned
by this owner. Plans, inputs and runtime identity are validated by the caller.
"""

import copy
from dataclasses import dataclass, fields
import math


@dataclass(frozen=True)
class RuntimeBounds:
    """Explicit seconds; no unbounded defaults, retries or infinite sentinels."""

    startup: float
    connect: float
    transport: float
    close: float
    wait: float
    terminate_wait: float
    kill_wait: float

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            try:
                valid = type(value) in (int, float) and math.isfinite(value) and value > 0
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError("INVALID_RUNTIME_BOUND")


class OwnedRuntimeCleanupError(OSError):
    """One or more retained cleanup operations failed, even after later exit."""


class OwnedRuntime:
    """Acquire once; close transport before escalating bounded process waits.

    ``process_factory(plan, timeout=...)`` returns an owned process adapter.
    ``transport_factory(process=..., plan=..., timeout=...,
    transport_timeout=...)`` returns one connected API-shaped transport.

    Transport exposes ``close(timeout=...)``. Process exposes
    ``wait(timeout=...) -> int``, ``terminate(timeout=...)`` and
    ``kill(timeout=...)``. Close/terminate/kill return None. TimeoutError is the
    canonical adapter timeout; other exceptions are retained as errors and also
    trigger bounded escalation. No polling, reconnection or startup retry occurs.
    """

    def __init__(self, plan, *, bounds, process_factory, transport_factory):
        if type(bounds) is not RuntimeBounds:
            raise ValueError("INVALID_RUNTIME_BOUNDS")
        if not callable(process_factory) or not callable(transport_factory):
            raise ValueError("EXPLICIT_RUNTIME_FACTORIES_REQUIRED")
        self._plan = plan
        self._bounds = bounds
        self._process_factory = process_factory
        self._transport_factory = transport_factory
        self._process = None
        self._connection = None
        self._state = "NEW"
        self._lifecycle = []
        self._first_failure = None
        self._process_result = dict(state="UNOBSERVED", exit_code=None)

    @property
    def state(self):
        return self._state

    @property
    def lifecycle(self):
        return copy.deepcopy(self._lifecycle)

    @property
    def first_failure(self):
        return copy.deepcopy(self._first_failure)

    @property
    def finalization_process(self):
        return copy.deepcopy(self._process_result)

    @property
    def connection(self):
        if self._state != "CONNECTED":
            raise RuntimeError("CONNECTION_NOT_ACTIVE")
        return self._connection

    @property
    def simulation(self):
        return self.connection.simulation

    @property
    def lane(self):
        return self.connection.lane

    @property
    def vehicle(self):
        return self.connection.vehicle

    @property
    def trafficlight(self):
        return self.connection.trafficlight

    def simulationStep(self, *args, **kwargs):
        # The transport adapter enforces the transport timeout on each request.
        # Exceptions propagate unchanged: this owner cannot certify step aborts.
        return self.connection.simulationStep(*args, **kwargs)

    def _record(self, operation, timeout, *, error=None, exit_code=None):
        event = dict(operation=operation, timeout_seconds=timeout,
                     outcome=("TIMEOUT" if isinstance(error, TimeoutError) else "ERROR")
                     if error is not None else "COMPLETED")
        if error is not None:
            event["exception"] = type(error).__name__
        if exit_code is not None:
            event["exit_code"] = exit_code
        self._lifecycle.append(event)
        if error is not None and self._first_failure is None:
            self._first_failure = copy.deepcopy(event)

    def start(self):
        """No retry after success or failure, including a failed factory call."""
        if self._state != "NEW":
            raise RuntimeError("RUNTIME_ALREADY_ATTEMPTED")
        self._state = "STARTING"
        operation, timeout = "PROCESS_START", self._bounds.startup
        try:
            self._process = self._process_factory(self._plan, timeout=timeout)
            if self._process is None:
                raise TypeError("PROCESS_HANDLE_REQUIRED")
            self._process_result = dict(state="NOT_EXITED", exit_code=None)
            self._record(operation, timeout)
            operation, timeout = "TRANSPORT_CONNECT", self._bounds.connect
            self._connection = self._transport_factory(
                process=self._process, plan=self._plan, timeout=timeout,
                transport_timeout=self._bounds.transport)
            if self._connection is None:
                raise TypeError("CONNECTION_HANDLE_REQUIRED")
            self._record(operation, timeout)
        except BaseException as error:
            self._record(operation, timeout, error=error)
            # Preserve the acquisition exception; cleanup evidence stays visible.
            try:
                self.close()
            except BaseException:
                pass
            raise
        self._state = "CONNECTED"
        return self._connection

    def close(self, wait=True):
        """Finalize owned handles exactly once; do not hide cleanup failures.

        A second close performs no operation and returns None. First-call errors
        remain available in lifecycle/first_failure. Even cancellation proceeds
        through the finite cleanup sequence before the cancellation is re-raised.
        """
        if wait is not True:
            raise ValueError("OWNERSHIP_REQUIRES_FINAL_WAIT")
        if self._state == "CLOSED":
            return None
        if self._state == "CLOSING":
            raise RuntimeError("CLEANUP_ALREADY_IN_PROGRESS")
        self._state = "CLOSING"
        errors = []

        def attempt(operation, timeout, call, expect_exit=False):
            try:
                result = call(timeout=timeout)
                if expect_exit:
                    if type(result) is not int:
                        raise TypeError("PROCESS_EXIT_CODE_REQUIRED")
                    self._process_result = dict(state="EXITED", exit_code=result)
                elif result is not None:
                    raise TypeError("CLEANUP_MUST_RETURN_NONE")
                self._record(operation, timeout, exit_code=result if expect_exit else None)
                return True
            except BaseException as error:
                self._record(operation, timeout, error=error)
                errors.append(error)
                return False

        try:
            if self._connection is not None:
                # Getters are included in the attempt so missing methods do not
                # bypass cleanup of the independently acquired process handle.
                attempt("TRANSPORT_CLOSE", self._bounds.close,
                        lambda **kw: self._connection.close(**kw))
            if self._process is not None:
                exited = attempt("PROCESS_WAIT", self._bounds.wait,
                                 lambda **kw: self._process.wait(**kw), True)
                if not exited:
                    attempt("PROCESS_TERMINATE", self._bounds.close,
                            lambda **kw: self._process.terminate(**kw))
                    exited = attempt("PROCESS_WAIT_AFTER_TERMINATE", self._bounds.terminate_wait,
                                     lambda **kw: self._process.wait(**kw), True)
                if not exited:
                    attempt("PROCESS_KILL", self._bounds.close,
                            lambda **kw: self._process.kill(**kw))
                    attempt("PROCESS_WAIT_AFTER_KILL", self._bounds.kill_wait,
                            lambda **kw: self._process.wait(**kw), True)
        finally:
            self._state = "CLOSED"
        if errors:
            for error in errors:
                if not isinstance(error, Exception):
                    raise error
            raise OwnedRuntimeCleanupError("OWNED_RUNTIME_CLEANUP_INCOMPLETE") from None
        return None
