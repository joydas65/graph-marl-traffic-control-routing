"""One supervised native worker's concrete factories and evidence handoff.

Importing this module performs no native work. Native defaults require a LIVE
plan and the supervisor's already-established ownership gate; offline tests must
inject both factories and remain SYNTHETIC. The supervisor, not a timeout passed
to Popen, bounds a factory that blocks before returning its child handle.
"""

import copy
from dataclasses import asdict
import math
import os
import time

from . import evidence as io, finalization as final, integration as core
from . import live_binding as live
from .owned_runtime import RuntimeBounds


RESULT_NAME = "native-worker-result.json"


def _require(ok, code):
    if not ok:
        raise ValueError(code)


def _deadline(clock, seconds):
    now = clock()
    _require(type(now) in (int, float) and math.isfinite(now), "WORKER_CLOCK")
    end = now + seconds
    _require(math.isfinite(end), "WORKER_DEADLINE")
    return end


def _remaining(clock, deadline):
    now = clock()
    _require(type(now) in (int, float) and math.isfinite(now), "WORKER_CLOCK")
    remaining = deadline - now
    if remaining <= 0:
        raise TimeoutError("WORKER_DEADLINE_EXPIRED")
    return remaining


class _NativeProcess:
    """One actual Popen handle; never signal a process name or unrelated group."""

    def __init__(self, process, clock):
        self.process, self.clock = process, clock
        self.pid = process.pid
        self.exit_code = None

    def wait(self, *, timeout):
        deadline = _deadline(self.clock, timeout)
        code = self.process.wait(timeout=_remaining(self.clock, deadline))
        _require(type(code) is int, "NATIVE_EXIT_CODE")
        self.exit_code = code  # Observed reaping remains true even on late return.
        _remaining(self.clock, deadline)
        return code

    def terminate(self, *, timeout):
        deadline = _deadline(self.clock, timeout)
        _remaining(self.clock, deadline)
        if self.exit_code is None:
            self.process.terminate()
        _remaining(self.clock, deadline)

    def kill(self, *, timeout):
        deadline = _deadline(self.clock, timeout)
        _remaining(self.clock, deadline)
        if self.exit_code is None:
            self.process.kill()
        _remaining(self.clock, deadline)


def _spawn_native(plan, *, deadline, clock):
    """Concrete acquisition, used only behind execute_worker's ownership gate.

    Worker bootstrap establishes RLIMIT_FSIZE before GO. Child log descriptors
    are write-once, no-follow files; the child inherits that finite per-file bound
    and the supervised process group. No detach/session/preexec escape is used.
    """
    import subprocess
    descriptors = []
    acquired, first, cleanup = None, None, []
    try:
        with io._directory(plan.output_path) as (directory, _):
            for name in ("original-stdout.log", "original-stderr.log"):
                descriptors.append(os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                           | os.O_NOFOLLOW, 0o600, dir_fd=directory))
        # Popen has no creation timeout. The already-owning supervisor independently
        # enforces startup expiry, including a child whose handle never returns.
        _remaining(clock, deadline)
        process = subprocess.Popen(plan.argv, stdin=subprocess.DEVNULL,
                                   stdout=descriptors[0], stderr=descriptors[1],
                                   close_fds=True)
        acquired = _NativeProcess(process, clock)
    except BaseException as error:
        first = error
    for descriptor in descriptors:
        try:
            os.close(descriptor)
        except BaseException as error:
            cleanup.append(dict(operation="CLOSE_LOG_DESCRIPTOR", exception=type(error).__name__))
            if first is None:
                first = error
    if first is not None:
        first.native_cleanup = cleanup
        if acquired is not None:
            # The factory failed after acquisition. Preserve the exact returned
            # handle so its caller can clean it without a second launch.
            first.unreturned_process = acquired
        raise first
    return acquired


def _after_finalization_notice(finalize, operation):
    """A broken reporting channel must not prevent actual close/reaping."""
    first = None
    try:
        finalize()
    except BaseException as error:
        first = error
    try:
        result = operation()
    except BaseException as error:
        if first is None:
            raise
        first.cleanup_findings = [dict(operation="AFTER_FINALIZE_NOTICE",
                                       exception=type(error).__name__)]
        raise first
    if first is not None:
        raise first
    return result


class _ObservedProcess:
    """Keep actual returned-exit observations separate from timeout labels."""

    def __init__(self, target, finalize):
        self.target, self.finalize = target, finalize
        self.exit_code = None
        self._pid = getattr(target, "pid", None)

    @property
    def pid(self):
        return self._pid

    def wait(self, *, timeout):
        def wait():
            code = self.target.wait(timeout=timeout)
            _require(type(code) is int, "NATIVE_EXIT_CODE")
            self.exit_code = code
            return code
        return _after_finalization_notice(self.finalize, wait)

    def terminate(self, *, timeout):
        return self.target.terminate(timeout=timeout)

    def kill(self, *, timeout):
        return self.target.kill(timeout=timeout)

    @property
    def reaped(self):
        return (type(self.exit_code) is int
                or type(getattr(self.target, "exit_code", None)) is int)

    @property
    def wait_evidence(self):
        # Not the broader late-return/reaped hint. Only an actual returned wait
        # on this retained child supplies the terminal-shortcut evidence.
        if (type(self.pid) is int and self.pid > 1 and
                type(getattr(self.target, "pid", None)) is int and
                getattr(self.target, "pid", None) == self.pid and
                type(self.exit_code) is int):
            return dict(pid=self.pid, exit_code=self.exit_code, wait_returned=True)
        return None


class _FinalizingTransport:
    """One close boundary, not a per-getter proxy or client modification."""

    def __init__(self, target, finalize):
        self.target, self.finalize = target, finalize

    def __getattr__(self, name):
        return getattr(self.target, name)

    def close(self, *, timeout):
        return _after_finalization_notice(self.finalize,
                                           lambda: self.target.close(timeout=timeout))


def execute_worker(plan, bounds, emit, *, process_factory=None,
                   transport_factory=None, clock=time.monotonic,
                   owned_scope_verified=False, startup_deadline=None,
                   total_deadline=None, cleanup_token=None, worker_pid=None):
    """Run one owned acquisition and hand off a bounded, independently read receipt.

    A normal return is a small DONE payload, not an experiment PASS. On error the
    original exception propagates with ``worker_failure`` attached for the sole
    supervisor ERROR receipt. Forced termination cannot produce this normal
    return and cannot manufacture a schema-2 cutoff or finalization record.
    """
    _require(owned_scope_verified is True, "OWNED_SCOPE_REQUIRED")
    _require(type(bounds) is RuntimeBounds and callable(emit), "WORKER_ARGUMENTS")
    injected = process_factory is not None or transport_factory is not None
    _require(not injected or (callable(process_factory) and callable(transport_factory)),
             "BOTH_OFFLINE_FACTORIES_REQUIRED")
    _require(plan.evidence_kind == ("SYNTHETIC" if injected else "LIVE"),
             "WORKER_FACTORY_ORIGIN_MISMATCH")
    has_cleanup_context = cleanup_token is not None or worker_pid is not None
    _require((injected and not has_cleanup_context) or
             (type(cleanup_token) is str and len(cleanup_token) == 32 and
              all(c in '0123456789abcdef' for c in cleanup_token) and
              type(worker_pid) is int and worker_pid > 1), "WORKER_CLEANUP_CONTEXT")
    for deadline in (startup_deadline, total_deadline):
        _require(deadline is None or (type(deadline) in (int, float) and math.isfinite(deadline)),
                 "WORKER_ABSOLUTE_DEADLINE")
    _require(injected or (startup_deadline is not None and total_deadline is not None),
             "SUPERVISOR_DEADLINES_REQUIRED")
    def check_total():
        if total_deadline is not None:
            _remaining(clock, total_deadline)
    def bounded_deadline(seconds, cap=None):
        deadline = _deadline(clock, seconds)
        for bound in (cap, total_deadline):
            if bound is not None:
                deadline = min(deadline, bound)
        return deadline
    check_total()
    if startup_deadline is not None:
        _remaining(clock, startup_deadline)
    live.validate_plan(plan)
    references = final.ReferenceContext(())
    state = dict(process=None, launches=0, finalizing=False, first_failure=None,
                 observation=None, assessment=None, receipt=None, unreturned_cleanup=[],
                 reporting_errors=[], native_cleanup=[], phase="START")

    def first_failure(value):
        if state["first_failure"] is None and value is not None:
            state["first_failure"] = copy.deepcopy(value)
            try:
                emit(dict(type="FIRST_FAILURE", failure=copy.deepcopy(value)))
            except BaseException as error:
                # Lost reporting cannot mask the original failure or prevent
                # cleanup of a late child/connection. Bootstrap still gets it.
                state["reporting_errors"].append(type(error).__name__)

    def finalize():
        if not state["finalizing"]:
            state["finalizing"] = True
            state["phase"] = "FINALIZE"
            # Parent caps this phase once against its fixed finalization/total
            # deadline; subsequent waits cannot reset it.
            try:
                emit(dict(type="PHASE", phase="FINALIZE"))
            except BaseException as error:
                state["reporting_errors"].append(type(error).__name__)
                raise

    def clean_unreturned(process):
        # A late handle is not handed to OwnedRuntime. Its factory must finish
        # bounded cleanup or leave an explicit unresolved outcome to the parent.
        try:
            finalize()
        except BaseException:
            # finalize has recorded the reporting failure. Continue with the
            # exact child handle; the chronological acquisition error remains.
            pass
        for operation, timeout in (("terminate", bounds.close),
                                   ("wait", bounds.terminate_wait),
                                   ("kill", bounds.close), ("wait", bounds.kill_wait)):
            try:
                result = getattr(process, operation)(timeout=timeout)
                state["unreturned_cleanup"].append(dict(operation=operation, outcome="COMPLETED"))
                if operation == "wait" and type(result) is int:
                    return
            except BaseException as error:
                state["unreturned_cleanup"].append(dict(operation=operation, outcome="ERROR",
                                                        exception=type(error).__name__))

    def start(plan, *, timeout):
        _require(state["launches"] == 0, "SECOND_CHILD_LAUNCH_FORBIDDEN")
        state["launches"] += 1
        deadline = bounded_deadline(timeout, startup_deadline)
        try:
            target = (process_factory(plan, timeout=_remaining(clock, deadline)) if injected
                      else _spawn_native(plan, deadline=deadline, clock=clock))
        except BaseException as error:
            state["native_cleanup"].extend(getattr(error, "native_cleanup", []))
            acquired = getattr(error, "unreturned_process", None)
            if acquired is not None:
                process = _ObservedProcess(acquired, finalize)
                state["process"] = process
                first_failure(dict(kind="OPERATIONAL", stage="PROCESS_START", code=type(error).__name__))
                clean_unreturned(process)
            raise
        _require(target is not None, "PROCESS_HANDLE_REQUIRED")
        process = _ObservedProcess(target, finalize)
        state["process"] = process
        try:
            _remaining(clock, deadline)
            if process.pid is not None:
                _require(type(process.pid) is int and process.pid > 0, "NATIVE_CHILD_PID")
                emit(dict(type="CHILD", pid=process.pid))
        except BaseException as error:
            first_failure(dict(kind="OPERATIONAL", stage="PROCESS_START", code=type(error).__name__))
            clean_unreturned(process)
            raise
        return process

    def connect(*, process, plan, timeout, transport_timeout):
        deadline = bounded_deadline(timeout)
        state["phase"] = "CONNECT"
        emit(dict(type="PHASE", phase="CONNECT", deadline=deadline))
        if injected:
            transport = transport_factory(process=process, plan=plan,
                                          timeout=_remaining(clock, deadline),
                                          transport_timeout=transport_timeout)
        else:
            from .native_transport import connect_native
            def exchange(kind, absolute_deadline):
                _require(kind in ("BEGIN", "END"), "WORKER_EXCHANGE_KIND")
                if state["phase"] in ("RUN", "FINALIZE"):
                    if kind == "BEGIN":
                        check_total()
                    deadline = min(absolute_deadline, total_deadline) if total_deadline is not None else absolute_deadline
                    emit(dict(type="EXCHANGE_" + kind, deadline=deadline))
            transport = connect_native(process, plan, _remaining(clock, deadline),
                                       transport_timeout, clock=clock, on_exchange=exchange)
        _require(transport is not None, "CONNECTION_HANDLE_REQUIRED")
        wrapped = _FinalizingTransport(transport, finalize)
        try:
            _remaining(clock, deadline)
            state["phase"] = "RUN"
            emit(dict(type="PHASE", phase="RUN"))
        except BaseException as error:
            first_failure(dict(kind="OPERATIONAL", stage="TRANSPORT_CONNECT", code=type(error).__name__))
            try:
                wrapped.close(timeout=bounds.close)
                state["unreturned_cleanup"].append(dict(operation="LATE_TRANSPORT_CLOSE", outcome="COMPLETED"))
            except BaseException as cleanup:
                state["unreturned_cleanup"].append(dict(operation="LATE_TRANSPORT_CLOSE", outcome="ERROR",
                                                        exception=type(cleanup).__name__))
            raise
        return wrapped

    def summary(assessment):
        return dict(measurement_status=assessment["measurement"]["measurement_status"],
                    stop_status=assessment["stop_status"],
                    reason_codes=copy.deepcopy(assessment["reason_codes"]))

    try:
        observed = live.observe_owned(plan, bounds=bounds, process_factory=start,
                                      transport_factory=connect, references=references)
        state["observation"] = observed
        first_failure(observed.run["failure"] or observed.ownership["first_failure"])
        check_total()
        assessment = core.assess_run(observed.run, references=references)
        state["assessment"] = summary(assessment)
        if assessment["stop_status"] is not None:
            first_failure(dict(kind="INTEGRITY" if assessment["stop_status"] == "FAIL" else "EVIDENCE",
                               stage="ASSESSMENT", code="WORKER_RUN_ASSESSMENT_STOP"))
        check_total()
        payload = {**io.PAYLOAD_BASE, "evidence_kind": plan.evidence_kind}
        if assessment["measurement"]["measurement_status"] == "VALID" and assessment["stop_status"] is None:
            payload.update(record_kind="RUN", record=observed.run)
        else:
            payload.update(record_kind="FAILURE", record=dict(
                failure_code="WORKER_RUN_ASSESSMENT_STOP",
                measurement_status=assessment["measurement"]["measurement_status"],
                experiment_status=assessment["stop_status"], run=observed.run, raw_evidence=None))
        receipt = io.write_once(plan.output_path, RESULT_NAME, payload, references=references)
        state["receipt"] = receipt
        check_total()
        _require(io.readback(receipt, references=references) == payload, "WORKER_READBACK_MISMATCH")
        check_total()
        process = state["process"]
        cleanup_handoff = None
        if (has_cleanup_context and process is not None and process.wait_evidence is not None and
                state["launches"] == 1 and observed.run["finalization"]["process"] ==
                dict(state="EXITED", exit_code=process.wait_evidence["exit_code"])):
            cleanup_handoff = dict(version=1, run_id=plan.run_id,
                condition_label=plan.condition, evidence_kind=plan.evidence_kind,
                binding_sha256=core.digest(plan.binding), output_directory=plan.output_directory,
                worker_pid=worker_pid, token=cleanup_token, child_launches=state["launches"],
                child_wait=process.wait_evidence if process is not None else None,
                finalization_process=copy.deepcopy(observed.run["finalization"]["process"]))
        return dict(receipt=receipt, grants=[asdict(grant) for grant in references._grants],
                    child_reaped=state["process"] is not None and state["process"].reaped,
                    assessment=state["assessment"], first_failure=state["first_failure"],
                    cleanup_handoff=cleanup_handoff)
    except BaseException as error:
        first_failure(getattr(error, "ownership_evidence", {}).get("first_failure") or
                      dict(kind="OPERATIONAL", stage="WORKER", code=type(error).__name__))
        observed = state["observation"]
        failure = dict(exception=type(error).__name__, first_failure=state["first_failure"],
                       child_reaped=state["process"] is not None and state["process"].reaped,
                       ownership=observed.ownership if observed is not None
                       else getattr(error, "ownership_evidence", None),
                       unreturned_cleanup=state["unreturned_cleanup"],
                       native_cleanup=state["native_cleanup"],
                       reporting_errors=state["reporting_errors"],
                       assessment=state["assessment"], receipt=state["receipt"])
        error.worker_failure = failure
        raise


def validate_cleanup_handoff(plan, done, *, worker_pid, child_pid, token):
    """Small in-memory closure from the trusted worker's current GO/DONE pipe.

    Correlation is not attestation against a compromised worker. The fixed
    factory covers one inherited-scope child, never arbitrary descendants.
    Full scientific receipt readback remains outside critical cleanup.
    """
    _handoff_references(plan, done)
    handoff = done.get("cleanup_handoff")
    _require(type(handoff) is dict and set(handoff) == {
        "version", "run_id", "condition_label", "evidence_kind", "binding_sha256",
        "output_directory", "worker_pid", "token", "child_launches", "child_wait",
        "finalization_process"}, "CLEANUP_HANDOFF_SCHEMA")
    _require(type(handoff["version"]) is int and handoff["version"] == 1 and
             type(token) is str and len(token) == 32 and
             all(c in '0123456789abcdef' for c in token) and
             handoff["token"] == token and type(worker_pid) is int and worker_pid > 1 and
             type(handoff["worker_pid"]) is int and handoff["worker_pid"] == worker_pid,
             "CLEANUP_HANDOFF_WORKER_BINDING")
    _require((handoff["run_id"], handoff["condition_label"], handoff["evidence_kind"],
              handoff["binding_sha256"], handoff["output_directory"]) ==
             (plan.run_id, plan.condition, plan.evidence_kind, core.digest(plan.binding),
              plan.output_directory), "CLEANUP_HANDOFF_RUN_BINDING")
    wait = handoff["child_wait"]
    _require(type(handoff["child_launches"]) is int and handoff["child_launches"] == 1 and
             type(child_pid) is int and child_pid > 1 and child_pid != worker_pid and
             done.get("child_reaped") is True and type(wait) is dict and set(wait) == {
                 "pid", "exit_code", "wait_returned"} and
             type(wait["pid"]) is int and wait["pid"] == child_pid and
             type(wait["exit_code"]) is int and wait["wait_returned"] is True,
             "CLEANUP_HANDOFF_CHILD_WAIT")
    process = handoff["finalization_process"]
    _require(type(process) is dict and set(process) == {"state", "exit_code"} and
             process["state"] == "EXITED" and type(process["exit_code"]) is int and
             process["exit_code"] == wait["exit_code"], "CLEANUP_HANDOFF_PROCESS_CONTRADICTION")


def _handoff_references(plan, done):
    """Validate already-received identities/shape only; never open evidence."""
    _require(type(done) is dict and set(done) == {
        "receipt", "grants", "child_reaped", "assessment", "first_failure", "cleanup_handoff"},
        "WORKER_DONE_SCHEMA")
    _require(type(done["child_reaped"]) is bool, "WORKER_CHILD_REAPING")
    _require(type(done["grants"]) is list and len(done["grants"]) == 1, "WORKER_GRANT_COUNT")
    raw_grant = done["grants"][0]
    _require(type(raw_grant) is dict and set(raw_grant) == {
        "run_id", "condition_label", "binding_sha256", "output_directory", "expected", "evidence_kind"},
        "WORKER_GRANT_SCHEMA")
    grant = final.ReferenceGrant(**raw_grant)
    _require((grant.run_id, grant.condition_label, grant.binding_sha256,
              grant.output_directory, grant.evidence_kind) ==
             (plan.run_id, plan.condition, core.digest(plan.binding),
              plan.output_directory, plan.evidence_kind) and grant.expected is not None,
             "WORKER_GRANT_BINDING")
    references = final.ReferenceContext((grant,))
    receipt = done["receipt"]
    _require(type(receipt) is dict and set(receipt) == {
        "schema_version", "evidence_kind", "ready_to_run", "persistence_status",
        "output_directory", "name", "format", "sha256", "byte_count"} and
             type(receipt["schema_version"]) is int and receipt["schema_version"] == 1 and
             receipt["ready_to_run"] is False and receipt["persistence_status"] == "VERIFIED" and
             type(receipt["sha256"]) is str and io.SHA256.fullmatch(receipt["sha256"]) and
             type(receipt["byte_count"]) is int and 0 < receipt["byte_count"] <= io.MAX_BYTES and
             receipt.get("name") == RESULT_NAME
             and receipt.get("output_directory") == plan.output_directory
             and receipt.get("evidence_kind") == plan.evidence_kind
             and receipt.get("format") == "JSON", "WORKER_RECEIPT_BINDING")
    assessment = done["assessment"]
    _require(type(assessment) is dict and set(assessment) == {
        "measurement_status", "stop_status", "reason_codes"} and
             assessment["measurement_status"] in ("VALID", "EVIDENCE_DEFICIENCY", "INTEGRITY_FAILURE") and
             assessment["stop_status"] in (None, "FAIL", "BLOCKED") and
             type(assessment["reason_codes"]) is list and
             all(type(code) is str for code in assessment["reason_codes"]) and
             (done["first_failure"] is None or type(done["first_failure"]) is dict),
             "WORKER_HANDOFF_ASSESSMENT_SCHEMA")
    return references


def validate_worker_result(plan, done):
    """Independently read one completed handoff using the explicit worker grant.

    No directory discovery or inferred authorization from a stored run occurs.
    This post-cleanup readback is ordinary bounded-size filesystem I/O, not a
    claim of a hard real-time filesystem guarantee under arbitrary OS failure.
    """
    live.validate_plan(plan)
    references = _handoff_references(plan, done)
    receipt = done["receipt"]
    payload = io.readback(receipt, references=references)
    _require(payload["record_kind"] in ("RUN", "FAILURE"), "WORKER_RECORD_KIND")
    run = payload["record"] if payload["record_kind"] == "RUN" else payload["record"]["run"]
    _require(type(run) is dict and run["run_id"] == plan.run_id
             and run["condition_label"] == plan.condition and run["binding"] == plan.binding
             and run["evidence_kind"] == plan.evidence_kind, "WORKER_RUN_BINDING")
    assessed = core.assess_run(run, references=references)
    summary = dict(measurement_status=assessed["measurement"]["measurement_status"],
                   stop_status=assessed["stop_status"], reason_codes=assessed["reason_codes"])
    _require(done["assessment"] == summary, "WORKER_ASSESSMENT_MISMATCH")
    _require(done["child_reaped"] == (run["finalization"]["process"]["state"] == "EXITED"),
             "WORKER_CHILD_REAPING")
    handoff = done["cleanup_handoff"]
    if handoff is not None:
        _require(type(handoff) is dict and type(handoff.get("child_wait")) is dict,
                 "CLEANUP_HANDOFF_SCHEMA")
        validate_cleanup_handoff(plan, done, worker_pid=handoff.get("worker_pid"),
                                 child_pid=handoff["child_wait"].get("pid"), token=handoff.get("token"))
        _require(handoff["finalization_process"] == run["finalization"]["process"],
                 "CLEANUP_HANDOFF_READBACK_CONTRADICTION")
    expected_failure = run["failure"]
    if expected_failure is None and assessed["stop_status"] is not None:
        expected_failure = dict(kind="INTEGRITY" if assessed["stop_status"] == "FAIL" else "EVIDENCE",
                                stage="ASSESSMENT", code="WORKER_RUN_ASSESSMENT_STOP")
    _require(done["first_failure"] == expected_failure, "WORKER_FIRST_FAILURE_MISMATCH")
    return payload
