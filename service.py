"""Bounded local reference integration for the qualified CPU GEMM worker."""
import argparse
import hashlib
import http.server
import json
import math
import os
import pathlib
import signal
import socketserver
import subprocess
import threading
import time
from worker import WorkerSnapshot, WorkerStopped

CONFIGS={'compact':{'workers':1,'max_dimension':128,'timeout':2.0},
         'throughput':{'workers':4,'max_dimension':256,'timeout':2.0}}
MAX_BODY=1024*1024

class RequestError(ValueError): pass

def validate_request(body, config):
    if not isinstance(body,dict) or set(body)!={'api_version','id','m','n','k','a','b'}:
        raise RequestError('schema: exact fields required')
    if body['api_version']!=1 or type(body['api_version']) is not int:
        raise RequestError('version: supported api_version=1')
    if not isinstance(body['id'],str) or not 1<=len(body['id'])<=64:
        raise RequestError('input: id must contain 1..64 characters')
    m,n,k=(body[x] for x in ['m','n','k'])
    if any(type(x) is not int or x<1 or x>config['max_dimension'] for x in [m,n,k]):
        raise RequestError('resource: dimension outside configured limit')
    for values,size in [(body['a'],m*k),(body['b'],k*n)]:
        if not isinstance(values,list) or len(values)!=size: raise RequestError('input: matrix length')
        if any(type(x) not in (int,float) or abs(x)>1000 or not math.isfinite(x) for x in values):
            raise RequestError('input: finite matrix elements within +/-1000 required')
    return m,n,k

class Server(socketserver.ThreadingMixIn,http.server.HTTPServer):
    daemon_threads=True
    allow_reuse_address=False
    def __init__(self,address,binary,config,log=None):
        self.binary=pathlib.Path(binary).resolve(); self.config=CONFIGS[config].copy()
        self.slots=threading.BoundedSemaphore(32); self.log=log
        self.lifecycle=threading.Condition();self.draining=False;self.active=0
        self.counts={'accepted':0,'completed':0,'failed':0,'rejected':0}
        self.write_lock=threading.Lock(); self.config_name=config
        self.worker=WorkerSnapshot(self.binary);self.binary_sha256=self.worker.digest
        try:super().__init__(address,Handler)
        except BaseException:self.worker.close();raise
    def admit(self):
        with self.lifecycle:
            if self.draining or self.active>=self.config['workers']:
                self.counts['rejected']+=1;return False
            self.active+=1;self.counts['accepted']+=1;return True
    def complete(self,status):
        with self.lifecycle:
            self.active-=1;self.counts['completed' if status==200 else 'failed']+=1;self.lifecycle.notify_all()
    def begin_drain(self):
        with self.lifecycle:self.draining=True;self.lifecycle.notify_all()
    def status(self):
        with self.lifecycle:return dict(self.counts,active=self.active,draining=self.draining)
    def drain(self,timeout):
        self.begin_drain()
        with self.lifecycle:finished=self.lifecycle.wait_for(lambda:self.active==0,timeout)
        if not finished:
            self.worker.stop()
            with self.lifecycle:finished=self.lifecycle.wait_for(lambda:self.active==0,2)
        return finished
    def shutdown_gracefully(self,timeout=3):
        finished=self.drain(timeout);self.shutdown();self.server_close();return finished
    def server_close(self):
        super().server_close();self.worker.close()
    def process_request(self,request,client_address):
        if not self.slots.acquire(blocking=False):
            try: request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\nRetry-After: 1\r\n\r\n')
            finally: self.shutdown_request(request)
            return
        try: super().process_request(request,client_address)
        except BaseException:
            self.slots.release(); raise
    def process_request_thread(self,request,client_address):
        try: super().process_request_thread(request,client_address)
        finally: self.slots.release()

class Handler(http.server.BaseHTTPRequestHandler):
    def setup(self):
        super().setup(); self.connection.settimeout(3)
    def log_message(self,*args): pass
    def reply(self,code,body):
        data=json.dumps(body,allow_nan=False,separators=(',',':')).encode()
        self.send_response(code); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data))); self.end_headers()
        try: self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError): pass
    def do_GET(self):
        if self.path=='/live':return self.reply(200,{'alive':True})
        if self.path=='/ready':return self.reply(503 if self.server.draining else 200,self.server.status())
        if self.path=='/metrics':return self.reply(200,self.server.status())
        if self.path!='/health': return self.reply(404,{'error':'route'})
        self.reply(200,{'api_version':1,'config':self.server.config_name,
                        'worker_sha256':self.server.binary_sha256,'limits':self.server.config})
    def do_POST(self):
        if self.path!='/v1/gemm': return self.reply(404,{'error':'route'})
        started=time.time_ns(); event_id='invalid'; status=500; acquired=False
        try:
            if self.headers.get('Transfer-Encoding'): raise RequestError('input: chunked bodies unsupported')
            lengths=self.headers.get_all('Content-Length',[])
            if len(lengths)!=1: raise RequestError('input: one Content-Length required')
            size=int(lengths[0])
            if size<1 or size>MAX_BODY:
                status=413; return self.reply(status,{'error':'resource: body limit'})
            raw=self.rfile.read(size)
            if len(raw)!=size: raise RequestError('input: incomplete body')
            body=json.loads(raw); m,n,k=validate_request(body,self.server.config); event_id=body['id']
            acquired=self.server.admit()
            if not acquired:
                status=503; return self.reply(status,{'error':'resource: workers occupied; retry with backoff'})
            data=' '.join(map(str,body['a']+body['b']))
            p=self.server.worker.run(['optimized',str(m),str(n),str(k),'1','0','stdin'],data,self.server.config['timeout'])
            if p.returncode: status=502; return self.reply(status,{'error':'worker failed','returncode':p.returncode})
            try:
                answer=json.loads(p.stdout)
                if type(answer.get('protocol')) is not int or answer['protocol']!=1 or len(answer['values'])!=m*n:raise ValueError()
                if any(type(x) not in (int,float) or abs(x)>1e12 or not math.isfinite(x) for x in answer['values']):raise ValueError()
                if len(answer['kernel_us'])!=1 or type(answer['kernel_us'][0]) not in (int,float) or not 0<answer['kernel_us'][0]<1e12:raise ValueError()
            except (ValueError,TypeError,KeyError,AttributeError,OverflowError) as e:raise RuntimeError('worker output contract') from e
            status=200
            self.reply(status,{'id':event_id,'api_version':1,'values':answer['values'],
                    'kernel_us':answer['kernel_us'][0],'worker_sha256':self.server.binary_sha256})
        except (ValueError,RequestError) as e:
            status=400; self.reply(status,{'error':str(e)})
        except subprocess.TimeoutExpired:
            status=504; self.reply(status,{'error':'worker deadline exceeded'})
        except PermissionError:
            status=502; self.reply(status,{'error':'worker permission denied'})
        except (OSError,KeyError,RuntimeError):
            status=502; self.reply(status,{'error':'worker unavailable or invalid response'})
        finally:
            if acquired: self.server.complete(status)
            if self.server.log:
                event={'event_id':event_id,'started_unix_ns':started,'finished_unix_ns':time.time_ns(),'http_status':status}
                with self.server.write_lock:
                    with open(self.server.log,'a') as f: f.write(json.dumps(event)+'\n')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--binary',default='build/gemm'); ap.add_argument('--port',type=int,default=8080)
    ap.add_argument('--config',choices=CONFIGS,default='compact'); ap.add_argument('--log');ap.add_argument('--drain-seconds',type=float,default=3);args=ap.parse_args()
    if not 0<args.drain_seconds<=60:ap.error('drain-seconds must be in (0,60]')
    server=Server(('127.0.0.1',args.port),args.binary,args.config,args.log)
    print(json.dumps({'address':server.server_address,'config':args.config}),flush=True)
    shutdown_threads=[]
    def stop(signum,frame):
        if shutdown_threads:return
        server.begin_drain()
        t=threading.Thread(target=server.shutdown_gracefully,args=(args.drain_seconds,));shutdown_threads.append(t);t.start()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:server.serve_forever()
    finally:
        for t in shutdown_threads:t.join()
        server.server_close()

if __name__=='__main__': main()
