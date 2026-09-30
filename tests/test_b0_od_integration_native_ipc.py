"""Actual native pipe/bootstrap calls with OS and process doubles only."""
import hashlib
import json
import signal
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.b0.od_integration_v1 import native_supervisor as n
from test_b0_od_integration_live_binding import Fixture, BOUNDS


class Clock:
    def __init__(self):
        self.now = 0.
    def __call__(self):
        return self.now


def handle():
    return SimpleNamespace(pid=43210, returncode=None,
        stdin=SimpleNamespace(fileno=lambda:91,close=Mock()),
        stdout=SimpleNamespace(fileno=lambda:92,close=Mock()),wait=Mock(return_value=0))


class NativeIPCTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock()
        self.ops=n.NativeIPC('/synthetic/python','0'*64,clock=self.clock)
        self.h=handle()
        self.ops._handles.append(self.h)
        self.ops._handle_pids[id(self.h)]=self.h.pid
        self.ops._verified_handles.add(id(self.h))

    def test_bootstrap_calls_actual_popen_shape_once_with_owned_session(self):
        f=Fixture(); self.addCleanup(f.close)
        created=[]
        def popen(argv,**kwargs):
            created.append((argv,kwargs)); return self.h
        self.ops=n.NativeIPC(f.plan.executable,f.plan.executable_sha256,clock=self.clock,popen=popen)
        with patch.object(n.os,'set_blocking') as blocking, patch.object(n.signal,'getsignal',return_value=signal.SIG_DFL):
            self.assertIs(self.ops.bootstrap(f.plan,n.SupervisorBounds(BOUNDS,2,20,4,3)),self.h)
        self.assertEqual(len(created),1)
        argv,kw=created[0]
        self.assertEqual(argv[1:4],['-I','-S','-B'])
        self.assertEqual(argv[-1],'--worker')
        self.assertTrue(kw['start_new_session']); self.assertTrue(kw['close_fds'])
        self.assertEqual(kw['bufsize'],0)
        self.assertNotIn('preexec_fn',kw); self.assertNotIn('shell',kw)
        self.assertEqual(blocking.call_args_list[0].args,(91,False))
        self.assertEqual(blocking.call_args_list[1].args,(92,False))
        self.assertEqual(self.ops.request['plan']['evidence_kind'],'SYNTHETIC')
        self.h.wait.assert_not_called()

    def test_post_handle_setup_failure_carries_owned_worker(self):
        f=Fixture(); self.addCleanup(f.close)
        self.ops=n.NativeIPC(f.plan.executable,f.plan.executable_sha256,popen=lambda *a,**k:self.h)
        with patch.object(n.os,'set_blocking',side_effect=OSError('synthetic setup')):
            with self.assertRaises(OSError) as caught:
                self.ops.bootstrap(f.plan,n.SupervisorBounds(BOUNDS,2,20,4,3))
        self.assertIs(caught.exception.worker_handle,self.h)
        self.h.wait.assert_not_called()

    def test_wrong_python_identity_never_calls_process_factory(self):
        f=Fixture(); self.addCleanup(f.close); factory=Mock()
        self.ops=n.NativeIPC(f.plan.executable,'0'*64,popen=factory)
        with self.assertRaisesRegex(ValueError,'PYTHON_IDENTITY'):
            self.ops.bootstrap(f.plan,n.SupervisorBounds(BOUNDS,2,20,4,3))
        factory.assert_not_called()

    def test_bootstrap_close_failure_does_not_mask_setup_failure_or_handle(self):
        f=Fixture(); self.addCleanup(f.close)
        self.ops=n.NativeIPC(f.plan.executable,f.plan.executable_sha256,popen=lambda *a,**k:self.h)
        first=ValueError('synthetic setup first')
        original_close=n.os.close
        failed=[False]
        def configure(*args):
            failed[0]=True
            raise first
        def close(fd):
            original_close(fd)
            if failed[0]:
                raise OSError('synthetic late descriptor failure')
        with patch.object(n.os,'set_blocking',side_effect=configure), patch.object(n.os,'close',side_effect=close):
            with self.assertRaises(ValueError) as caught:
                self.ops.bootstrap(f.plan,n.SupervisorBounds(BOUNDS,2,20,4,3))
        self.assertIs(caught.exception,first)
        self.assertIs(first.worker_handle,self.h)
        self.assertEqual(first.bootstrap_cleanup_failures,['OSError'])

    def test_finish_attempts_both_pipes_and_preserves_first_close_failure(self):
        first=OSError('synthetic first close')
        self.h.stdin.close.side_effect=first
        self.h.stdout.close.side_effect=ValueError('synthetic later close')
        with self.assertRaises(OSError) as caught:
            self.ops.finish(self.h)
        self.assertIs(caught.exception,first)
        self.h.stdout.close.assert_called_once()
        self.h.wait.assert_not_called()

    def test_custom_sigchld_handler_never_calls_process_factory(self):
        f=Fixture(); self.addCleanup(f.close); factory=Mock()
        self.ops=n.NativeIPC(f.plan.executable,f.plan.executable_sha256,popen=factory)
        with patch.object(n.signal,'getsignal',return_value=signal.SIG_IGN):
            with self.assertRaisesRegex(ValueError,'REAPING'):
                self.ops.bootstrap(f.plan,n.SupervisorBounds(BOUNDS,2,20,4,3))
        factory.assert_not_called()

    def test_scope_verified_from_os_not_ipc_fields(self):
        with patch.object(n.os,'getpgid',return_value=self.h.pid) as group, patch.object(n.os,'getsid',return_value=self.h.pid) as session:
            self.assertTrue(self.ops.verify_scope(self.h))
            group.assert_called_once_with(self.h.pid); session.assert_called_once_with(self.h.pid)
        with patch.object(n.os,'getpgid',return_value=54321):
            self.assertFalse(self.ops.verify_scope(self.h))

    def test_partial_send_has_one_deadline_and_late_send_is_rejected(self):
        budgets=[]; writes=[]
        def ready(r,w,e,budget):
            budgets.append(budget); return [],w,[]
        def send(fd,raw):
            writes.append((fd,raw)); self.clock.now+=.3; return 1
        self.ops.selector=ready
        with patch.object(n.os,'write',side_effect=send):
            with self.assertRaises(TimeoutError):
                self.ops.send(self.h,{'type':'CONTROL'},1.)
        self.assertEqual(len(writes),4)
        self.assertTrue(all(fd==91 for fd,_ in writes))
        self.assertLessEqual(sum(budgets),.4+1e-9)

    def test_complete_go_is_framed_once_and_carries_frozen_request(self):
        self.ops.request={'plan':{'evidence_kind':'SYNTHETIC'},'bounds':{'total':2}}
        self.ops.selector=lambda r,w,e,t:([],w,[])
        chunks=[]
        def send(fd,raw):
            chunks.append(raw[:3]); return min(3,len(raw))
        with patch.object(n.os,'write',side_effect=send):
            self.ops.send(self.h,{'type':'GO','total_deadline':2},1.)
        raw=b''.join(chunks)
        self.assertEqual(raw.count(b'\n'),1)
        self.assertEqual(json.loads(raw)['plan'],self.ops.request['plan'])

    def test_continuing_partial_receive_cannot_extend_message_deadline(self):
        self.ops.selector=lambda r,w,e,t:(r,[],[])
        def receive(fd,count):
            self.clock.now+=.3; return b'x'
        with patch.object(n.os,'read',side_effect=receive):
            for _ in range(3):
                self.assertIsNone(self.ops.receive(self.h,1.))
            with self.assertRaises(TimeoutError):
                self.ops.receive(self.h,1.)

    def test_buffered_messages_and_eof_are_not_blocking_reads(self):
        self.ops.selector=lambda r,w,e,t:(r,[],[])
        with patch.object(n.os,'read',return_value=b'{"type":"A"}\n{"type":"B"}\n') as read:
            self.assertEqual(self.ops.receive(self.h,1.),{'type':'A'})
            self.assertEqual(self.ops.receive(self.h,1.),{'type':'B'})
            self.assertEqual(read.call_count,1)
        with patch.object(n.os,'read',return_value=b''):
            with self.assertRaises(EOFError): self.ops.receive(self.h,1.)

    def test_message_size_guard_does_not_read_unbounded_bytes(self):
        self.ops.buffer=b'x'*self.ops.MAX_MESSAGE
        self.ops.selector=lambda r,w,e,t:(r,[],[])
        with patch.object(n.os,'read',return_value=b'x') as read:
            with self.assertRaisesRegex(ValueError,'IPC_MESSAGE_TOO_LARGE'):
                self.ops.receive(self.h,1.)
            read.assert_called_once_with(92,1)

    def test_completion_tail_rejects_buffered_bytes_without_another_read(self):
        for raw in (b'{"type":"COMPLETION_ARMED"}\n',b'{'):
            with self.subTest(raw_length=len(raw)):
                self.ops.buffer=raw
                self.ops.selector=Mock(side_effect=AssertionError('buffered bytes need no select'))
                with patch.object(n.os,'read',side_effect=AssertionError('unexpected read')) as read:
                    self.assertEqual(self.ops.completion_tail(self.h,1.),
                                     {'state':'TRAILING','byte_count':len(raw)})
                read.assert_not_called()
        self.h.wait.assert_not_called()

    def test_completion_tail_reads_only_bounded_owned_pipe_bytes(self):
        self.ops.selector=lambda r,w,e,t:(r,[],[])
        with patch.object(n.os,'read',return_value=b'x') as read:
            self.assertEqual(self.ops.completion_tail(self.h,1.),
                             {'state':'TRAILING','byte_count':1})
        read.assert_called_once_with(92,min(4096,self.ops.MAX_MESSAGE))
        self.assertEqual(self.ops.buffer,b'x')
        self.h.wait.assert_not_called()

    def test_completion_tail_quiet_observation_does_not_reset_grace(self):
        self.clock.now=.75
        budgets=[]
        def quiet(readable,writable,exceptional,budget):
            self.assertEqual(readable,[92])
            self.assertEqual(writable,[])
            budgets.append(budget)
            self.clock.now+=budget
            return [],[],[]
        self.ops.selector=quiet
        with patch.object(n.os,'read',side_effect=AssertionError('not readable')) as read:
            self.assertEqual(self.ops.completion_tail(self.h,1.),{'state':'QUIET'})
        self.assertEqual(self.clock.now,1.)
        self.assertAlmostEqual(sum(budgets),.25)
        read.assert_not_called()
        self.h.wait.assert_not_called()

    def test_completion_tail_eof_reports_channel_only_not_worker_cleanup(self):
        self.ops.selector=lambda r,w,e,t:(r,[],[])
        with patch.object(n.os,'read',return_value=b''):
            self.assertEqual(self.ops.completion_tail(self.h,1.),{'state':'EOF'})
        self.h.wait.assert_not_called()
        self.assertIsNone(self.h.returncode)

    def test_completion_tail_interrupted_reads_keep_original_grace(self):
        def ready(r,w,e,budget):
            self.clock.now+=budget
            return r,[],[]
        self.ops.selector=ready
        with patch.object(n.os,'read',side_effect=[BlockingIOError(),InterruptedError(),b'']) as read:
            self.assertEqual(self.ops.completion_tail(self.h,1.),{'state':'EOF'})
        self.assertEqual(read.call_count,3)
        self.assertAlmostEqual(self.clock.now,.3)
        self.h.wait.assert_not_called()

    def test_completion_tail_read_error_remains_visible(self):
        self.ops.selector=lambda r,w,e,t:(r,[],[])
        with patch.object(n.os,'read',side_effect=PermissionError('synthetic pipe denial')):
            with self.assertRaises(PermissionError):
                self.ops.completion_tail(self.h,1.)
        self.h.wait.assert_not_called()

    def test_completion_marker_partial_frame_needs_newline_before_original_deadline(self):
        plan=SimpleNamespace(run_id='synthetic-framed-completion',binding={'fixture':'framing'})
        candidate={'synthetic_candidate':True}
        marker=n._completion_marker(plan,candidate,worker_pid=self.h.pid,token='0'*32)
        raw=json.dumps(marker,separators=(',',':')).encode()+b'\n'
        for deadline,expires in ((1.,False),(.5,True)):
            with self.subTest(deadline=deadline):
                self.clock.now=0.
                self.ops.buffer=b''
                def ready(r,w,e,budget):
                    return r,[],[]
                pieces=iter((raw[:15],raw[15:-1],raw[-1:]))
                def read(fd,count):
                    self.assertEqual(fd,92)
                    self.clock.now+=.2
                    return next(pieces)
                self.ops.selector=ready
                with patch.object(n.os,'read',side_effect=read):
                    self.assertIsNone(self.ops.receive(self.h,deadline))
                    self.assertIsNone(self.ops.receive(self.h,deadline))
                    self.assertNotIn(b'\n',self.ops.buffer)
                    if expires:
                        with self.assertRaises(TimeoutError):
                            self.ops.receive(self.h,deadline)
                    else:
                        received=self.ops.receive(self.h,deadline)
                        self.assertEqual(received,marker)
                        n._validate_completion_marker(received,plan,candidate,
                            worker_pid=self.h.pid,token='0'*32)
                self.assertAlmostEqual(self.clock.now,.6)
        self.h.wait.assert_not_called()

    def test_group_and_worker_signals_target_only_retained_handle(self):
        with patch.object(n.os,'killpg') as group, patch.object(n.os,'kill') as worker:
            self.ops.signal_group(self.h,'TERM'); self.ops.signal_group(self.h,'KILL')
            self.ops.signal_worker(self.h,'TERM')
            self.assertEqual([c.args for c in group.call_args_list],[(43210,signal.SIGTERM),(43210,signal.SIGKILL)])
            worker.assert_called_once_with(43210,signal.SIGTERM)
        self.h.wait.assert_not_called()

    def test_wait_uses_remaining_budget_and_finish_cannot_wait(self):
        self.clock.now=.75
        self.assertEqual(self.ops.reap(self.h,1.),0)
        self.h.wait.assert_called_once_with(timeout=.25)
        self.ops.finish(self.h)
        self.h.stdin.close.assert_called_once(); self.h.stdout.close.assert_called_once()
        self.assertEqual(self.h.wait.call_count,1)

    def test_invalid_monotonic_values_cannot_disable_deadline(self):
        for value in (True,float('nan'),float('inf'),10**1000):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValueError): n.remaining(value,self.clock)

    def actual_worker_handoff(self, errors):
        from scripts.b0.od_integration_v1.native_worker import execute_worker,validate_worker_result
        f=Fixture(errors=errors); self.addCleanup(f.close)
        messages=[{'type':'READY','pid':self.h.pid}]
        done=execute_worker(f.plan,BOUNDS,messages.append,process_factory=f.process_factory,
            transport_factory=f.transport_factory,clock=self.clock,owned_scope_verified=True)
        messages.append({'type':'DONE',**done})
        h=self.h; clock=self.clock; calls=[]
        class Ops:
            def bootstrap(self,*args): return h
            def verify_scope(self,handle): return handle is h
            def send(self,handle,message,deadline):
                calls.append(message['type'])
                messages.append(n._completion_marker(f.plan,done,
                    worker_pid=h.pid,token=message['cleanup_token']))
            def receive(self,handle,deadline): return messages.pop(0)
            def signal_group(self,handle,sig): calls.append(sig)
            def signal_worker(self,*args): raise AssertionError('unverified scope')
            def pause(self,deadline): clock.now=deadline
            def completion_tail(self,handle,deadline): return {'state':'QUIET'}
            def reap(self,handle,deadline): return -15
            def finish(self,handle): pass
        result=n.supervise(f.plan,n.SupervisorBounds(BOUNDS,2,20,10,3),ops=Ops(),clock=clock)
        payload=validate_worker_result(f.plan,result['worker_result'])
        self.assertNotIn('type',result['worker_result'])
        self.assertEqual(calls,['GO','TERM','KILL'])
        self.assertTrue(result['normal_finalization'])
        self.assertEqual(payload['evidence_kind'],'SYNTHETIC')
        return result,payload

    def test_actual_worker_supervisor_and_independent_writer_positive_handoff(self):
        result,payload=self.actual_worker_handoff(b'')
        self.assertEqual(result['status'],'WORKER_COMPLETED')
        self.assertEqual(payload['record_kind'],'RUN')
        self.assertEqual(payload['record']['measurement']['measurement_status'],'VALID')

    def test_actual_worker_late_integrity_failure_survives_supervisor_handoff(self):
        result,payload=self.actual_worker_handoff(b'Error: synthetic late native-shaped error\n')
        self.assertEqual(result['status'],'COMPLETED_WITH_FAILURE')
        self.assertIsNotNone(result['first_failure'])
        self.assertEqual(payload['record_kind'],'FAILURE')
        self.assertEqual(payload['record']['experiment_status'],'FAIL')
