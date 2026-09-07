import concurrent.futures,fcntl,json,pathlib,tempfile,threading,time,unittest,urllib.error,urllib.request,subprocess,sys,select
from service import Server
from scripts.install import install
from scripts.validate import case,request,correct
from worker import WorkerSnapshot

class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.binary=install()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.temp.name)
        self.server=Server(('127.0.0.1',0),self.binary,'compact');self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):self.server.shutdown_gracefully(.2);self.thread.join(3);self.temp.cleanup()
    def fixture(self,script):
        p=self.path/'worker';p.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo "gemm-cpu-contract/1 fixed"; exit 0; fi\n'+script+'\n');p.chmod(0o700)
        self.server.worker.close();self.server.worker=WorkerSnapshot(p)
    def wait_active(self):
        deadline=time.monotonic()+2
        while self.server.status()['active']==0 and time.monotonic()<deadline:time.sleep(.005)
        self.assertEqual(self.server.status()['active'],1)
    def test_path_replacement_does_not_change_snapshot_or_result(self):
        p=self.path/'copied';p.write_bytes(self.binary.read_bytes());p.chmod(0o700)
        original=self.server.worker;self.server.worker=WorkerSnapshot(p)
        try:
            sha=self.server.worker.digest;p.write_text('#!/bin/sh\nexit 99\n');p.chmod(0o700)
            body=case(2,'snapshot');r=request(self.url,body);self.assertTrue(correct(body,r));self.assertEqual(r['body']['worker_sha256'],sha)
            with self.assertRaises(OSError):__import__('os').pwrite(self.server.worker.fd,b'bad',0)
        finally:self.server.worker.close();self.server.worker=original
    def test_drain_rejects_new_work_and_preserves_inflight(self):
        self.fixture('sleep .2\nprintf \'{"protocol":1,"values":[6],"kernel_us":[1]}\\n\'')
        body={'api_version':1,'id':'active','m':1,'n':1,'k':1,'a':[2],'b':[3]}
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            f=pool.submit(request,self.url,body);self.wait_active();self.server.begin_drain()
            with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(self.url+'/ready')
            self.assertEqual(err.exception.code,503)
            err.exception.close()
            self.assertEqual(request(self.url,body)['status'],503)
            self.assertTrue(self.server.drain(1));self.assertEqual(f.result()['body']['values'],[6])
        self.assertEqual(self.server.status()['active'],0);self.assertEqual(self.server.status()['completed'],1)
    def test_drain_deadline_kills_and_reaps_worker(self):
        self.fixture('exec sleep 30');self.server.config['timeout']=40
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            f=pool.submit(request,self.url,case(1,'deadline'));self.wait_active();start=time.monotonic()
            self.assertTrue(self.server.drain(.05));self.assertLess(time.monotonic()-start,2)
            self.assertEqual(f.result()['status'],502)
        self.assertFalse(self.server.worker.processes);self.assertEqual(self.server.status()['failed'],1)
    def test_worker_timeout_releases_admission(self):
        self.fixture('exec sleep 5');self.server.config['timeout']=.05
        self.assertEqual(request(self.url,case(1,'timeout'))['status'],504)
        self.assertEqual(self.server.status()['active'],0);self.assertFalse(self.server.worker.processes)
    def test_malformed_worker_output_is_backend_failure(self):
        self.fixture('printf \'{"protocol":true,"values":[6],"kernel_us":[1]}\\n\'')
        self.assertEqual(request(self.url,case(1,'malformed'))['status'],502)

    def test_cli_sigterm_drains_an_accepted_request(self):
        p=self.path/'signal-worker'
        p.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo "gemm-cpu-contract/1 fixed"; exit 0; fi\nsleep .4\nprintf \'{"protocol":1,"values":[6],"kernel_us":[1]}\\n\'\n')
        p.chmod(0o700)
        child=subprocess.Popen([sys.executable,'service.py','--binary',str(p),'--port','0','--drain-seconds','2'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertTrue(select.select([child.stdout],[],[],5)[0],'CLI did not report readiness')
            url='http://127.0.0.1:'+str(json.loads(child.stdout.readline())['address'][1])
            body={'api_version':1,'id':'signal','m':1,'n':1,'k':1,'a':[2],'b':[3]}
            with concurrent.futures.ThreadPoolExecutor(1) as pool:
                f=pool.submit(request,url,body)
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    with urllib.request.urlopen(url+'/metrics',timeout=1) as r:state=json.load(r)
                    if state['active']==1:break
                    time.sleep(.005)
                self.assertEqual(state['active'],1)
                child.terminate()
                self.assertEqual(f.result(timeout=3)['body']['values'],[6])
            child.communicate(timeout=3);self.assertEqual(child.returncode,0)
        finally:
            if child.poll() is None:child.kill()
            child.communicate(timeout=3)
