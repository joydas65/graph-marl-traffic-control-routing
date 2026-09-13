"""One gated POSIX worker, never a pool or a per-getter proxy.

The initial Popen/OS bootstrap is NOT deadline-interruptible. No SUMO acquisition
is authorized until an unreaped worker PID=PGID=SID has been verified. After GO,
this research-process supervisor independently bounds worker work and IPC.
Importing this module does not launch a helper, SUMO, or any socket.
"""
from dataclasses import asdict, dataclass, fields
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import select
import signal
import sys
import time

# Explicit isolated worker-file invocation; no installed-package or global
# socket modification. Normal research-process imports do not alter sys.path.
if __name__ == '__main__' and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    __package__ = 'scripts.b0.od_integration_v1'

from . import evidence as io
from .owned_runtime import RuntimeBounds


@dataclass(frozen=True)
class SupervisorBounds:
    runtime: RuntimeBounds
    bootstrap: float
    total: float
    finalize: float
    cleanup: float

    def __post_init__(self):
        if type(self.runtime) is not RuntimeBounds:
            raise ValueError('RUNTIME_BOUNDS_REQUIRED')
        for field in fields(self):
            if field.name == 'runtime':
                continue
            value = getattr(self, field.name)
            try:
                valid = type(value) in (float, int) and math.isfinite(value) and value > 0
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError('FINITE_SUPERVISOR_BOUND_REQUIRED')


def remaining(deadline, clock):
    now = clock()
    try:
        valid = all(type(v) in (float,int) and math.isfinite(v) for v in (deadline,now))
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('FINITE_MONOTONIC_DEADLINE_REQUIRED')
    value = deadline - now
    if value <= 0:
        raise TimeoutError('ABSOLUTE_DEADLINE_EXPIRED')
    return value


def supervise(plan, bounds, *, ops, clock=time.monotonic, cancelled=lambda: False):
    """Production coordination with injectable OS/IPC/clock operations.

    Never consume worker status while further scope signalling is possible.
    A terminal observation alone never proves the owned child was reaped.
    Result is an operational receipt, not a schema-2 scientific run.
    """
    if type(bounds) is not SupervisorBounds:
        raise ValueError('SUPERVISOR_BOUNDS_REQUIRED')
    result = dict(record_kind='NATIVE_OPERATIONAL_RECEIPT', schema_version=1,
        run_id=plan.run_id, evidence_kind=plan.evidence_kind, ready_to_run=False,
        status='INTERRUPTED', first_failure=None, findings=[], worker_result=None,
        late_messages=[],
        ownership_verified=False, go_sent=False, worker_reaped=False,
        worker_exit_code=None, child_scope='UNRESOLVED', normal_finalization=False,
        terminal_cleanup=False, scope_signalling_disabled=False,
        worker_ownership_unresolved=False, worker_reap_within_deadline=False,
        bootstrap_limitation='PRE_HANDLE_OS_BOOTSTRAP_NOT_INTERRUPTIBLE')
    handle = None
    phase = 'BOOTSTRAP'
    deadline = clock() + bounds.bootstrap
    total_end = None
    exchange_end = None
    candidate = None
    owned_pid = None
    child_pid = None
    cleanup_token = None
    child_wait_verified = False
    terminal_exit_code = None

    def finding(operation, code, **extra):
        event = dict(operation=operation, code=code, **extra)
        result['findings'].append(event)
        return event

    def fail(operation, code, **extra):
        event = finding(operation, code, **extra)
        if result['first_failure'] is None:
            result['first_failure'] = event.copy()

    def check(limit):
        if cancelled():
            raise InterruptedError('SUPERVISOR_CANCELLED')
        remaining(limit, clock)

    def disable_signalling():
        # One-way, including when a later wait fails or consumes ownership.
        result['scope_signalling_disabled'] = True
        disable = getattr(ops, 'disable_signalling', None)
        if disable is not None:
            try:
                disable(handle)
            except BaseException as error:
                fail('CLEANUP', 'SIGNALLING_DISABLE_UNRESOLVED', exception=type(error).__name__)

    def observe_worker():
        if (type(owned_pid) is not int or owned_pid <= 1 or
                type(handle.pid) is not int or handle.pid != owned_pid or
                getattr(handle, 'returncode', None) is not None):
            observed = dict(state='UNSAFE', code='RETAINED_HANDLE_CHANGED_OR_REAPED')
        else:
            observe = getattr(ops, 'observe_worker', None)
            try:
                observed = (observe(handle) if observe is not None else
                            dict(state='UNAVAILABLE', code='NO_NONREAPING_FACILITY'))
            except ChildProcessError:
                observed = dict(state='UNSAFE', code='WORKER_REAPING_OWNERSHIP_LOST')
            except BaseException as error:
                fail('CLEANUP', 'WORKER_OBSERVATION_ERROR', exception=type(error).__name__)
                observed = dict(state='UNAVAILABLE', code='OBSERVATION_ERROR')
        if (type(observed) is not dict or observed.get('state') not in
                ('TERMINAL', 'NO_STATUS', 'UNAVAILABLE', 'UNSAFE')):
            observed = dict(state='UNSAFE', code='WORKER_OBSERVATION_SCHEMA')
        if observed['state'] == 'TERMINAL' and (
                type(observed.get('pid')) is not int or observed['pid'] != owned_pid or
                type(observed.get('exit_code')) is not int):
            observed = dict(state='UNSAFE', code='WORKER_OBSERVATION_IDENTITY')
        finding('CLEANUP', 'WORKER_NONREAPING_OBSERVATION', observation=observed)
        if observed['state'] == 'UNSAFE':
            result['worker_ownership_unresolved'] = True
            fail('CLEANUP', 'WORKER_OWNERSHIP_UNRESOLVED')
            disable_signalling()
        return observed

    try:
        # No claim that a later elapsed-time check interrupted this call.
        check(deadline)
        handle = ops.bootstrap(plan, bounds)
        owned_pid = handle.pid
        result['ownership_verified'] = ops.verify_scope(handle) is True
        if not result['ownership_verified']:
            raise RuntimeError('WORKER_SCOPE_NOT_VERIFIED')
        check(deadline)
        while candidate is None:
            active_end = min(deadline, exchange_end) if exchange_end is not None else deadline
            check(active_end)
            message = ops.receive(handle, active_end)
            # Bytes/handles arriving at or after expiry never restore success.
            try:
                check(active_end)
            except BaseException:
                if message is not None:
                    result['late_messages'].append(message)
                    finding(phase, 'LATE_MESSAGE_IGNORED', message_type=message.get('type')
                            if type(message) is dict else 'MALFORMED')
                raise
            if message is None:
                continue
            if type(message) is not dict or type(message.get('type')) is not str:
                raise ValueError('WORKER_MESSAGE_SCHEMA')
            kind = message['type']
            if kind == 'READY':
                if (phase != 'BOOTSTRAP' or type(message.get('pid')) is not int
                        or message['pid'] != handle.pid):
                    raise ValueError('WORKER_READY_IDENTITY_OR_ORDER')
                phase = 'STARTUP'
                started = clock()
                total_end = started + bounds.total
                deadline = min(total_end, started + bounds.runtime.startup)
                check(deadline)
                # A short fixed control message, not a scientific result payload.
                cleanup_token = os.urandom(16).hex()
                ops.send(handle, {'type':'GO', 'total_deadline':total_end,
                                 'startup_deadline':deadline,
                                 'cleanup_token':cleanup_token}, deadline)
                result['go_sent'] = True
                check(deadline)
            elif kind == 'CHILD':
                if (phase != 'STARTUP' or type(message.get('pid')) is not int or
                        message['pid'] <= 1 or message['pid'] == owned_pid):
                    raise ValueError('CHILD_MESSAGE_ORDER')
                if any(x['code'] == 'CHILD_HANDLE_REPORTED' for x in result['findings']):
                    raise ValueError('SECOND_CHILD_FORBIDDEN')
                # Observation only; never an authority for PID/group signalling.
                finding(phase, 'CHILD_HANDLE_REPORTED')
                child_pid = message['pid']
            elif kind == 'PHASE':
                new = message.get('phase')
                valid = ((phase == 'STARTUP' and new == 'CONNECT') or
                         (phase == 'CONNECT' and new == 'RUN') or
                         (phase in ('STARTUP','CONNECT','RUN') and new == 'FINALIZE'))
                if not valid or exchange_end is not None:
                    raise ValueError('WORKER_PHASE_ORDER')
                phase = new
                budget = {'CONNECT':bounds.runtime.connect, 'RUN':bounds.total,
                          'FINALIZE':bounds.finalize}[new]
                deadline = min(total_end, clock() + budget)
                supplied = message.get('deadline')
                if supplied is not None:
                    if type(supplied) not in (float,int) or not math.isfinite(supplied):
                        raise ValueError('PHASE_DEADLINE_SCHEMA')
                    deadline = min(deadline, supplied)
                check(deadline)
            elif kind == 'EXCHANGE_BEGIN':
                value = message.get('deadline')
                if (phase not in ('RUN','FINALIZE') or exchange_end is not None or
                        type(value) not in (float,int) or not math.isfinite(value)):
                    raise ValueError('EXCHANGE_ORDER_OR_DEADLINE')
                exchange_end = min(deadline, value, clock()+(
                    bounds.runtime.close if phase == 'FINALIZE' else bounds.runtime.transport))
                check(exchange_end)
            elif kind == 'EXCHANGE_END':
                if exchange_end is None or phase not in ('RUN','FINALIZE'):
                    raise ValueError('EXCHANGE_END_WITHOUT_BEGIN')
                check(exchange_end)
                exchange_end = None
            elif kind == 'FIRST_FAILURE':
                failure = message.get('failure')
                if type(failure) is not dict:
                    raise ValueError('WORKER_FAILURE_SCHEMA')
                fail(phase, 'WORKER_REPORTED_FAILURE', worker_failure=failure)
            elif kind == 'ERROR':
                result['worker_error'] = message
                fail(phase, 'WORKER_EXCEPTION', exception=message.get('exception'))
                raise RuntimeError('WORKER_EXCEPTION')
            elif kind == 'DONE':
                if phase != 'FINALIZE' or exchange_end is not None:
                    raise ValueError('DONE_BEFORE_FINALIZATION')
                candidate = {key:value for key,value in message.items() if key != 'type'}
                if candidate.get('cleanup_handoff') is not None:
                    # Only small already-delivered IPC data; no evidence-file IO.
                    from .native_worker import validate_cleanup_handoff
                    validate_cleanup_handoff(plan, candidate, worker_pid=owned_pid,
                                             child_pid=child_pid, token=cleanup_token)
                    child_wait_verified = True
                    finding(phase, 'OWNED_CHILD_WAIT_VERIFIED')
                else:
                    finding(phase, 'CHILD_WAIT_UNVERIFIED')
                check(active_end)
                result['worker_result'] = candidate
                result['normal_finalization'] = True
            else:
                raise ValueError('UNKNOWN_WORKER_MESSAGE')
    except BaseException as error:
        # A setup failure AFTER a handle exists must return ownership to cleanup.
        if handle is None and getattr(error, 'worker_handle', None) is not None:
            handle = error.worker_handle
            owned_pid = handle.pid
            try:
                result['ownership_verified'] = ops.verify_scope(handle) is True
            except BaseException:
                result['ownership_verified'] = False
        fail(phase, 'TIMEOUT' if isinstance(error, TimeoutError) else 'CANCELLED'
             if isinstance(error, (InterruptedError, KeyboardInterrupt)) else 'ERROR',
             exception=type(error).__name__)
        for name in getattr(error, 'bootstrap_cleanup_failures', ()):
            finding('BOOTSTRAP_CLEANUP', 'DESCRIPTOR_CLOSE_FAILED', exception=name)
        # candidate is never accepted through this path, even if files exist.
        candidate = None
        child_wait_verified = False
        result['normal_finalization'] = False
    finally:
        if handle is not None:
            cleanup_end = clock() + bounds.cleanup
            # Reserve some of the ONE cleanup budget for kill and worker wait.
            grace_end = min(cleanup_end, clock()+min(bounds.runtime.terminate_wait, bounds.cleanup/2))
            method = ops.signal_group if result['ownership_verified'] else ops.signal_worker
            for sig in ('TERM','KILL'):
                try:
                    remaining(cleanup_end, clock)
                    observed = observe_worker()
                    if result['scope_signalling_disabled']:
                        break
                    remaining(cleanup_end, clock)
                    if (sig == 'KILL' and result['ownership_verified'] and
                            child_wait_verified and candidate is not None and
                            observed['state'] == 'TERMINAL'):
                        if cancelled():
                            fail('CLEANUP', 'CANCELLED')
                            candidate = None
                        else:
                            disable_signalling()
                            result['terminal_cleanup'] = True
                            terminal_exit_code = observed['exit_code']
                            finding('CLEANUP', 'KILL_SKIPPED_VERIFIED_CHILD_WAIT_AND_TERMINAL_WORKER')
                            break
                    method(handle, sig)
                    finding('CLEANUP', 'SIGNAL_ATTEMPT_COMPLETED', signal=sig)
                except BaseException as error:
                    fail('CLEANUP', 'SIGNAL_UNRESOLVED', signal=sig,
                         exception=type(error).__name__,
                         errno=error.errno if type(getattr(error, 'errno', None)) is int else None)
                    if isinstance(error, ChildProcessError):
                        result['worker_ownership_unresolved'] = True
                        disable_signalling()
                if sig == 'TERM':
                    try:
                        ops.pause(grace_end)
                    except BaseException as error:
                        fail('CLEANUP', 'GRACE_INTERRUPTED', exception=type(error).__name__)
            # No more signalling after this point, including a failed wait.
            if not result['scope_signalling_disabled']:
                disable_signalling()
            try:
                if result['worker_ownership_unresolved']:
                    # Popen.wait may turn ECHILD into zero. Do not manufacture
                    # reaping evidence after our exclusive ownership was lost.
                    raise ChildProcessError('WORKER_OWNERSHIP_UNRESOLVED')
                remaining(cleanup_end, clock)
                code = ops.reap(handle, cleanup_end)
                if type(code) is not int:
                    raise ValueError('WORKER_EXIT_CODE_REQUIRED')
                result['worker_reaped'], result['worker_exit_code'] = True, code
                remaining(cleanup_end, clock)
                if result['terminal_cleanup'] and code != terminal_exit_code:
                    raise ValueError('WORKER_TERMINAL_REAP_CONTRADICTION')
                result['worker_reap_within_deadline'] = True
            except BaseException as error:
                fail('CLEANUP', 'WORKER_REAP_UNRESOLVED', exception=type(error).__name__)
            try:
                ops.finish(handle)
            except BaseException as error:
                fail('CLEANUP', 'IPC_CLOSE_UNRESOLVED', exception=type(error).__name__)
        try:
            if cancelled():
                fail('CLEANUP', 'CANCELLED')
                candidate = None
        except BaseException as error:
            fail('CLEANUP', 'CANCELLATION_CHECK_FAILED', exception=type(error).__name__)
            candidate = None
    if candidate is not None and child_wait_verified and result['worker_reap_within_deadline']:
        result['child_scope'] = 'REPORTED_CHILD_REAPED_AND_WORKER_REAPED'
    if candidate is not None and result['worker_reaped']:
        result['status'] = 'WORKER_COMPLETED' if result['first_failure'] is None else 'COMPLETED_WITH_FAILURE'
    # No aggregate PROCESS_STOPPED/absence claim follows a successful signal.
    return result


class NativeIPC:
    """Concrete nonblocking pipe operations. No process is created by __init__."""
    MAX_MESSAGE = 65536

    def __init__(self, python_executable, python_sha256, *, clock=time.monotonic,
                 popen=None, selector=select.select):
        self.python = str(python_executable)
        self.python_sha256 = python_sha256
        self.clock, self.popen, self.selector = clock, popen, selector
        self.buffer = b''
        self._handles = []  # keep unreaped handles alive throughout ownership
        self._handle_pids = {}
        self._verified_handles = set()
        self._signalling_disabled = set()

    def bootstrap(self, plan, bounds):
        from .live_binding import validate_plan
        validate_plan(plan)
        python = Path(self.python)
        if not python.is_absolute() or hashlib.sha256(python.read_bytes()).hexdigest() != self.python_sha256:
            raise ValueError('PYTHON_IDENTITY_MISMATCH')
        if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
            raise ValueError('EXCLUSIVE_DEFAULT_CHILD_REAPING_REQUIRED')
        self.request = {'plan':asdict(plan),'bounds':asdict(bounds)}
        if self.popen is None:
            import subprocess
            popen = subprocess.Popen
        else:
            popen = self.popen
        import subprocess
        # stderr is a bounded worker log via the worker's inherited FSIZE limit.
        with io._directory(plan.output_path) as (fd, _):
            log = os.open('worker-stderr.log', os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600, dir_fd=fd)
        handle = None
        first = None
        try:
            handle = popen([self.python,'-I','-S','-B',str(Path(__file__).resolve()),'--worker'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                start_new_session=True, close_fds=True, bufsize=0)
            self._handles.append(handle)
            self._handle_pids[id(handle)] = handle.pid
            os.set_blocking(handle.stdin.fileno(), False)
            os.set_blocking(handle.stdout.fileno(), False)
        except BaseException as error:
            first = error
        try:
            os.close(log)
        except BaseException as error:
            if first is None:
                first = error
            else:
                first.bootstrap_cleanup_failures = [type(error).__name__]
        if first is not None:
            if handle is not None:
                first.worker_handle = handle
            raise first
        return handle

    def verify_scope(self, handle):
        self._guard_handle(handle)
        verified = (type(handle.pid) is int and handle.pid > 1 and
                os.getpgid(handle.pid) == handle.pid and os.getsid(handle.pid) == handle.pid)
        if verified:
            self._verified_handles.add(id(handle))
        return verified

    def disable_signalling(self, handle):
        self._signalling_disabled.add(id(handle))

    def _guard_handle(self, handle):
        if (not any(item is handle for item in self._handles) or
                self._handle_pids.get(id(handle)) != handle.pid or
                type(handle.pid) is not int or handle.pid <= 1 or
                getattr(handle, 'returncode', None) is not None or
                id(handle) in self._signalling_disabled or
                signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL):
            self.disable_signalling(handle)
            raise ChildProcessError(errno.ECHILD, 'WORKER_OWNERSHIP_UNRESOLVED')

    def observe_worker(self, handle):
        """Non-consuming worker-only status; no group-absence/credential claim."""
        try:
            self._guard_handle(handle)
            names = ('waitid', 'P_PID', 'WEXITED', 'WNOHANG', 'WNOWAIT',
                     'CLD_EXITED', 'CLD_KILLED', 'CLD_DUMPED')
            if any(getattr(os, name, None) is None for name in names):
                return dict(state='UNAVAILABLE', code='NO_NONREAPING_FACILITY')
            value = os.waitid(os.P_PID, handle.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            self._guard_handle(handle)
        except ChildProcessError:
            self.disable_signalling(handle)
            return dict(state='UNSAFE', code='WORKER_REAPING_OWNERSHIP_LOST')
        except OSError as error:
            return dict(state='UNAVAILABLE', code='WAITID_ERROR',
                        exception=type(error).__name__, errno=error.errno)
        if value is None:
            return dict(state='NO_STATUS', code='NO_WORKER_STATUS_AVAILABLE')
        if type(value.si_pid) is not int or value.si_pid != handle.pid:
            self.disable_signalling(handle)
            return dict(state='UNSAFE', code='WAITID_WRONG_PID')
        if type(value.si_code) is not int or type(value.si_status) is not int:
            return dict(state='UNAVAILABLE', code='WAITID_STATUS_SCHEMA')
        if value.si_code == os.CLD_EXITED and 0 <= value.si_status <= 255:
            return dict(state='TERMINAL', pid=value.si_pid, exit_code=value.si_status)
        if value.si_code in (os.CLD_KILLED, os.CLD_DUMPED) and value.si_status > 0:
            return dict(state='TERMINAL', pid=value.si_pid, exit_code=-value.si_status)
        return dict(state='NO_STATUS', code='WORKER_NOT_OBSERVED_TERMINAL')

    def send(self, handle, message, deadline):
        if message.get('type') == 'GO':
            message = {**message, **self.request}
        raw = json.dumps(message, allow_nan=False, separators=(',',':')).encode()+b'\n'
        if len(raw) > self.MAX_MESSAGE:
            raise ValueError('IPC_MESSAGE_TOO_LARGE')
        offset = 0
        while offset < len(raw):
            budget = remaining(deadline, self.clock)
            _, ready, _ = self.selector([], [handle.stdin.fileno()], [], min(budget, .1))
            remaining(deadline, self.clock)
            if ready:
                try:
                    count = os.write(handle.stdin.fileno(), raw[offset:])
                except BlockingIOError:
                    continue
                if count <= 0:
                    raise EOFError('WORKER_CONTROL_PIPE_CLOSED')
                offset += count
        remaining(deadline, self.clock)

    def receive(self, handle, deadline):
        if b'\n' not in self.buffer:
            ready, _, _ = self.selector([handle.stdout.fileno()], [], [], min(remaining(deadline,self.clock), .1))
            remaining(deadline,self.clock)
            if not ready:
                return None
            try:
                chunk = os.read(handle.stdout.fileno(), min(4096,self.MAX_MESSAGE+1-len(self.buffer)))
            except BlockingIOError:
                return None
            if not chunk:
                raise EOFError('WORKER_STATUS_PIPE_CLOSED')
            self.buffer += chunk
            if len(self.buffer) > self.MAX_MESSAGE:
                raise ValueError('IPC_MESSAGE_TOO_LARGE')
            remaining(deadline,self.clock)
        if b'\n' not in self.buffer:
            return None
        line, self.buffer = self.buffer.split(b'\n',1)
        remaining(deadline,self.clock)
        return json.loads(line)

    def signal_group(self, handle, sig):
        # The caller has NOT reaped the leader; PID reuse is excluded under the
        # documented exclusive-child-reaper assumption. Never trust IPC PIDs.
        self._guard_handle(handle)
        if id(handle) not in self._verified_handles:
            self.disable_signalling(handle)
            raise ChildProcessError(errno.ECHILD, 'WORKER_SCOPE_NOT_VERIFIED')
        try:
            os.killpg(handle.pid, signal.SIGTERM if sig == 'TERM' else signal.SIGKILL)
        except ProcessLookupError:
            pass  # no absence claim; descendant reaping remains unestablished

    def signal_worker(self, handle, sig):
        self._guard_handle(handle)
        try:
            os.kill(handle.pid, signal.SIGTERM if sig == 'TERM' else signal.SIGKILL)
        except ProcessLookupError:
            pass

    def pause(self, deadline):
        while self.clock() < deadline:
            self.selector([],[],[],min(deadline-self.clock(), .1))

    def reap(self, handle, deadline):
        self.disable_signalling(handle)
        return handle.wait(timeout=remaining(deadline,self.clock))

    def finish(self, handle):
        # Unbuffered pipes; no flush, communicate, context-manager wait or join.
        first = None
        for stream in (handle.stdin,handle.stdout):
            try:
                stream.close()
            except BaseException as error:
                if first is None:
                    first = error
        if first is not None:
            raise first


def run_native(plan, bounds, *, python_executable, python_sha256,
               clock=time.monotonic, cancelled=lambda: False):
    """Concrete dormant entry point for ONE later-authorized LIVE run."""
    from .live_binding import validate_plan
    validate_plan(plan)
    if plan.evidence_kind != 'LIVE':
        raise ValueError('NATIVE_ENTRY_REQUIRES_LIVE_ORIGIN_NOT_AUTHORIZATION')
    ops = NativeIPC(python_executable,python_sha256,clock=clock)
    result = supervise(plan,bounds,ops=ops,clock=clock,cancelled=cancelled)
    if result['worker_result'] is not None and result['normal_finalization']:
        from .native_worker import validate_worker_result
        try:
            validate_worker_result(plan,result['worker_result'])
        except BaseException as error:
            event = dict(operation='POST_CLEANUP_READBACK',code='WORKER_RESULT_UNVERIFIED',
                         exception=type(error).__name__)
            result['findings'].append(event)
            if result['first_failure'] is None:
                result['first_failure'] = event.copy()
            result['status'] = 'RESULT_UNVERIFIED'
            result['normal_finalization'] = False
            # Keep historical cleanup decisions/actual worker wait observations,
            # but do not retain a positive child-scope claim after failed readback.
            result['child_scope'] = 'UNRESOLVED'
    # Explicit operational/interruption receipt, NOT a manufactured schema-2 run.
    raw = io._encode(result)
    with io._directory(plan.output_path) as (fd, _):
        io._create(fd,'native-operational-receipt.json',raw)
        if io._read(fd,'native-operational-receipt.json') != raw:
            raise OSError('OPERATIONAL_RECEIPT_READBACK')
    return result


def worker_main():
    """Gated private worker entry. Never called by offline tests or imports."""
    import resource
    from .live_binding import LaunchPlan
    from .native_worker import execute_worker
    pid = os.getpid()
    if os.getpgrp() != pid or os.getsid(0) != pid:
        raise RuntimeError('WORKER_NOT_SESSION_LEADER')
    resource.setrlimit(resource.RLIMIT_FSIZE,(io.MAX_BYTES,io.MAX_BYTES))
    def emit(message):
        raw = json.dumps(message,allow_nan=False,separators=(',',':')).encode()+b'\n'
        if len(raw)>NativeIPC.MAX_MESSAGE:
            raise ValueError('IPC_MESSAGE_TOO_LARGE')
        offset=0
        while offset<len(raw):
            count=os.write(1,raw[offset:])
            if count<=0:
                raise EOFError('SUPERVISOR_PIPE_CLOSED')
            offset+=count
    emit({'type':'READY','pid':pid})
    # Before GO, EOF aborts with no SUMO acquisition. Parent bootstrap deadline
    # covers a returned worker; it cannot interrupt pre-handle process creation.
    line=sys.stdin.buffer.readline(NativeIPC.MAX_MESSAGE+1)
    if not line.endswith(b'\n') or len(line)>NativeIPC.MAX_MESSAGE:
        return
    message=json.loads(line)
    if message.get('type')!='GO':
        return
    remaining(message['startup_deadline'],time.monotonic)
    data=message['plan']; data['argv']=tuple(data['argv'])
    plan=LaunchPlan(**data)
    b=message['bounds']; runtime=RuntimeBounds(**b.pop('runtime'))
    bounds=SupervisorBounds(runtime=runtime,**b)
    try:
        payload=execute_worker(plan,runtime,emit,clock=time.monotonic,owned_scope_verified=True,
            startup_deadline=message['startup_deadline'],total_deadline=message['total_deadline'],
            cleanup_token=message['cleanup_token'],worker_pid=pid)
        emit({'type':'DONE',**payload})
    except BaseException as error:
        emit({'type':'ERROR','exception':type(error).__name__,
              'worker_failure':getattr(error,'worker_failure',None)})
    # Stay unreaped as the PID reservation until the supervisor terminates this
    # exact group. EOF allows exit if the supervisor disappears; no new launch.
    sys.stdin.buffer.read(1)


if __name__ == '__main__':
    if sys.argv[1:] != ['--worker']:
        raise SystemExit('worker entry only')
    worker_main()
