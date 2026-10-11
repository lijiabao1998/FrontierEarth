"""Single CPU, zero-dollar, frozen-input launcher; one attempt, no implicit replay."""
import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True,type=Path);p.add_argument('--round',required=True)
    a=p.parse_args();repo=a.repo.resolve();record_path=repo/'runs'/a.round/'round.json'
    r=json.loads(record_path.read_text(encoding='utf-8'))
    if r.get('state')!='ADMITTED' or not r.get('admitted_at'):raise RuntimeError('NOT_RUN: no new-round admission')
    for relative,digest in r['execution_inputs_sha256'].items():
        path=(repo/relative).resolve()
        if not path.is_relative_to(repo) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise RuntimeError('frozen input changed: '+relative)
    now=dt.datetime.now(dt.timezone.utc)
    started=dt.datetime.fromisoformat(r['budget']['preparation_started_at'])
    remaining=min(1800,r['budget']['wall_minutes']*60-(now-started).total_seconds())
    if remaining<=0:raise RuntimeError('NOT_RUN: whole-round budget exhausted')
    if os.name=='nt':
        k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=ctypes.c_void_p
        k.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
        k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
        handle=k.GetCurrentProcess();mask=ctypes.c_size_t();system=ctypes.c_size_t()
        if not k.GetProcessAffinityMask(handle,ctypes.byref(mask),ctypes.byref(system)):raise ctypes.WinError(ctypes.get_last_error())
        chosen=mask.value & -mask.value
        if not k.SetProcessAffinityMask(handle,chosen):raise ctypes.WinError(ctypes.get_last_error())
        affinity={'mask':chosen,'cpu_count':chosen.bit_count(),'children_inherit':True}
    else:
        chosen=min(os.sched_getaffinity(0));os.sched_setaffinity(0,{chosen});affinity={'cpu':chosen,'cpu_count':1,'children_inherit':True}
    out=repo/'problems'/r['problem_id']/'results'/'independent_20261011'/'attempt-1'
    out.mkdir(parents=True,exist_ok=False)
    here=repo/'problems'/r['problem_id']/'experiments'/'independent_20261011'
    command=[sys.executable,'-X','utf8',str(here/'verify.py'),'--repo',str(repo),'--round',a.round,'--output',str(out/'result.json')]
    launch={'started_at':now.isoformat(),'command':command,'cwd':str(repo),'python':sys.version,'platform':platform.platform(),
            'affinity':affinity,'timeout_seconds':remaining,'usd':0,'replay':False}
    (out/'launch.json').write_text(json.dumps(launch,indent=2)+'\n',encoding='utf-8');print(json.dumps(launch),flush=True)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',PYTHONIOENCODING='utf-8',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    t0=time.perf_counter();timed_out=False;cleanup={}
    with (out/'stdout.txt').open('wb') as stdout,(out/'stderr.txt').open('wb') as stderr:
        remaining=r['budget']['wall_minutes']*60-(dt.datetime.now(dt.timezone.utc)-started).total_seconds()
        if remaining<=0:raise RuntimeError('NOT_RUN: deadline reached before Popen')
        child=subprocess.Popen(command,cwd=repo,env=env,stdout=stdout,stderr=stderr)
        try:code=child.wait(timeout=max(.001,r['budget']['wall_minutes']*60-(dt.datetime.now(dt.timezone.utc)-started).total_seconds()))
        except subprocess.TimeoutExpired:
            timed_out=True
            if os.name=='nt':
                try:
                    stop=subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=2)
                    (out/'termination.stdout.txt').write_bytes(stop.stdout);(out/'termination.stderr.txt').write_bytes(stop.stderr)
                    cleanup['taskkill_exit_code']=stop.returncode
                except subprocess.TimeoutExpired as exc:
                    (out/'termination.stdout.txt').write_bytes(exc.stdout or b'');(out/'termination.stderr.txt').write_bytes(exc.stderr or b'')
                    cleanup['taskkill_timeout']=True
            else:child.kill()
            try:child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                child.kill()
                try:child.wait(timeout=1)
                except subprocess.TimeoutExpired:cleanup['child_not_confirmed_terminated']=True
            code=124
    try:result=json.loads((out/'result.json').read_text(encoding='utf-8')) if (out/'result.json').exists() else None
    except Exception as exc:result=None;cleanup['result_parse_error']=str(exc);code=2
    execution={'finished_at':dt.datetime.now(dt.timezone.utc).isoformat(),'wall_seconds':time.perf_counter()-t0,
               'child_exit_code':code,'timed_out':timed_out,'cleanup':cleanup,'result_present':result is not None,
               'verdict':None if result is None else result.get('verdict',result.get('audit_verdict')),
               'status':'COMPLETED_WITH_RETAINED_FAILURE' if code==1 and result else 'COMPLETED' if code==0 and result else 'FAIL_CLOSED'}
    (out/'execution.json').write_text(json.dumps(execution,indent=2)+'\n',encoding='utf-8');print(json.dumps(execution),flush=True)
    return code

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        import traceback
        print(json.dumps({'status':'FAIL_CLOSED_NOT_RUN','error':str(exc)}),file=sys.stderr);traceback.print_exc();sys.exit(2)
