"""Focused stdlib safety harness; no subprocess/socket/runtime access permitted."""
import sys
import os
from pathlib import Path
import importlib.abc
import hashlib
import json
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT/'.local-evidence'/'b0-od-integration-public-v1'
OUTPUTS=WORKSPACE/'synthetic-test-outputs'
OUTPUTS.mkdir(parents=True, exist_ok=True)
tempfile.tempdir=str(OUTPUTS)
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
attempts=[]

class NoRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'traci','libsumo','sumolib','torch','numpy','boto3','botocore'}:
            attempts.append('RUNTIME_IMPORT'); raise RuntimeError('forbidden runtime import')
sys.meta_path.insert(0,NoRuntime())

def audit(event,args):
    if event.startswith(('subprocess.','socket.')) or event in {'os.system','os.posix_spawn','os.fork','os.exec','os.spawn'}:
        attempts.append('PROCESS_OR_SOCKET'); raise RuntimeError('forbidden process or socket')
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        raw=os.fsdecode(args[0]); path=Path(raw)
        # Descriptor-relative IO in the writer uses basename plus dir_fd; its
        # no-follow directory traversal anchors these under this workspace.
        if not path.is_absolute() and len(path.parts)==1: return
        absolute=path.absolute()
        if ROOT/'.local-evidence' in absolute.parents and not (absolute==WORKSPACE or WORKSPACE in absolute.parents):
            attempts.append('HISTORICAL_IGNORED_IO'); raise RuntimeError('ignored historical evidence read denied')
        mode=args[1]; flags=args[2]
        writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        if writing and not (absolute==WORKSPACE or WORKSPACE in absolute.parents):
            attempts.append('OUT_OF_SCOPE_WRITE'); raise RuntimeError('out-of-scope write denied')
sys.addaudithook(audit)

class Counted(unittest.TextTestResult):
    def __init__(self,*a,**k):
        super().__init__(*a,**k); self.passed=0; self.subtests=0
    def addSuccess(self,test): self.passed+=1; super().addSuccess(test)
    def addSubTest(self,test,subtest,error): self.subtests+=1; super().addSubTest(test,subtest,error)

def hashes():
    paths=sorted((ROOT/'scripts/b0/od_integration_v1').glob('*.py'))+sorted((ROOT/'tests').glob('test_b0_od_integration_*.py'))+[ROOT/'tests/b0_od_integration_fixtures.py',Path(__file__).resolve()]
    paths.append(ROOT/'tests/reference/b0_od_integration_v1_projection.json')
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def run(kind):
    loader=unittest.TestLoader(); before=hashes(); started=time.monotonic()
    if kind=='existing':
        suite=unittest.TestSuite()
        for path in sorted((ROOT/'tests').glob('test_b0*.py')):
            if not path.name.startswith('test_b0_od_integration_'):
                suite.addTests(loader.discover(str(ROOT/'tests'),pattern=path.name,top_level_dir=str(ROOT/'tests')))
    else: suite=loader.discover(str(ROOT/'tests'),pattern='test_b0_od_integration_*.py',top_level_dir=str(ROOT/'tests'))
    result=unittest.TextTestRunner(verbosity=2,resultclass=Counted).run(suite)
    report={'surface':kind,'tests':result.testsRun,'passed':result.passed,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'collection_errors':len(loader.errors),'subtests':result.subtests,'seconds':round(time.monotonic()-started,3),'source_hashes_unchanged':before==hashes(),'forbidden_attempts':list(attempts),'source_sha256':hashes()}
    print('OFFLINE_REPORT='+json.dumps(report),flush=True)
    return result.wasSuccessful() and not loader.errors and not attempts and before==hashes()

if __name__=='__main__':
    chosen=sys.argv[1] if len(sys.argv)>1 else 'new'
    if chosen not in ('new','existing'): raise SystemExit('only new or existing B0 surface allowed')
    raise SystemExit(0 if run(chosen) else 1)
