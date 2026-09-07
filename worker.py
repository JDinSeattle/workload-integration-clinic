"""Sealed Linux executable snapshots and tracked subprocess groups."""
import fcntl
import hashlib
import os
import pathlib
import signal
import subprocess
import threading

class WorkerStopped(RuntimeError): pass

class WorkerSnapshot:
    def __init__(self,path):
        path=pathlib.Path(path).resolve()
        if not os.access(path,os.X_OK): raise PermissionError('worker must be executable at installation')
        with path.open('rb') as f:
            data=f.read(16*1024*1024+1)
        if len(data)>16*1024*1024: raise ValueError('worker size limit')
        self.digest=hashlib.sha256(data).hexdigest()
        self.fd=os.memfd_create('qualified-worker',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
        self.lock=threading.Lock();self.processes={};self.stopped=False
        try:
            with os.fdopen(os.dup(self.fd),'wb') as f:f.write(data);f.flush()
            os.fchmod(self.fd,0o500)
            fcntl.fcntl(self.fd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL)
            p=self.run(['--version'],'',3)
            if p.returncode or p.stdout.strip()!='gemm-cpu-contract/1 fixed':raise ValueError('worker version incompatible')
        except BaseException:self.close();raise
    def run(self,args,data,timeout):
        with self.lock:
            if self.stopped or self.fd is None:raise WorkerStopped('worker draining')
            p=subprocess.Popen([f'/proc/self/fd/{self.fd}',*args],pass_fds=(self.fd,),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
            self.processes[p.pid]=p
        try:
            try:stdout,stderr=p.communicate(data,timeout=timeout)
            except subprocess.TimeoutExpired:
                self.kill(p);p.communicate(timeout=2);raise
            return subprocess.CompletedProcess(args,p.returncode,stdout,stderr)
        finally:
            with self.lock:self.processes.pop(p.pid,None)
    @staticmethod
    def kill(p):
        try:os.killpg(p.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    def stop(self):
        with self.lock:
            self.stopped=True
            for p in self.processes.values():self.kill(p)
    def close(self):
        self.stop()
        with self.lock:
            if self.fd is not None:os.close(self.fd);self.fd=None
