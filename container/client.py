"""Container-side real HTTP client, independent numerical oracle and environment probe."""
import argparse,concurrent.futures,errno,json,os,pathlib,statistics,subprocess,sys,time,urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.validate import case,request,correct

def hardening():
    errors={}
    for name,path in [('rootfs','/app/readonly-probe'),('worker','/app/build/gemm')]:
        try:
            fd=os.open(path,os.O_WRONLY,0o600);os.close(fd)
        except OSError as e:errors[name]=e.errno
        else:raise AssertionError('read-only probe unexpectedly writable: '+path)
    status=pathlib.Path('/proc/self/status').read_text();fields={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in status.splitlines() if ':' in line}
    cg={name:pathlib.Path('/sys/fs/cgroup',name).read_text().strip() for name in ['cpu.max','memory.max','memory.swap.max','pids.max']}
    assert os.geteuid()==10001 and fields['CapEff']=='0000000000000000' and fields['NoNewPrivs']=='1'
    assert errors['rootfs']==errno.EROFS and errors['worker'] in (errno.EROFS,errno.EACCES),errors
    return {'uid':os.geteuid(),'write_errno':errors,'status':{k:fields[k] for k in ['CapEff','NoNewPrivs','Seccomp']},'cgroup':cg}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=['health','load','smoke','hardening','memory-probe']);ap.add_argument('--url',default='http://api:8080');ap.add_argument('--config',default='compact');args=ap.parse_args()
    if args.op=='health':
        with urllib.request.urlopen(args.url+'/ready',timeout=1) as r:assert r.status==200
        return
    if args.op=='hardening':print(json.dumps(hardening()));return
    if args.op=='memory-probe':
        def events():return {k:int(v) for k,v in (line.split() for line in pathlib.Path('/sys/fs/cgroup/memory.events').read_text().splitlines())}
        limit=int(pathlib.Path('/sys/fs/cgroup/memory.max').read_text());assert limit==256*1024*1024
        before=events()
        child=subprocess.run([sys.executable,'-c',"open('/proc/self/oom_score_adj','w').write('1000'); a=bytearray(384*1024*1024); print(len(a))"],capture_output=True,text=True,timeout=15)
        after=events();assert child.returncode==-9 and after['oom_kill']>before['oom_kill'],(child.returncode,before,after)
        print(json.dumps({'memory_max':limit,'child_returncode':child.returncode,'events_before':before,'events_after':after,'oom_kill_delta':after['oom_kill']-before['oom_kill']}));return
    if args.op=='smoke':
        b=case(3,'smoke');r=request(args.url,b);assert correct(b,r);print(json.dumps(r));return
    rows=[];cohorts=[]
    for concurrency in [1,4,8]:
        bodies=[case(64,f'{args.config}-{concurrency}-{i}') for i in range(48)];start=time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(concurrency) as pool:results=list(pool.map(lambda b:request(args.url,b),bodies))
        duration=time.monotonic()-start
        for b,r in zip(bodies,results):
            assert r['status']==503 or correct(b,r),r
            r.pop('body');r.update(config=args.config,concurrency=concurrency);rows.append(r)
        times=sorted(r['e2e_ms'] for r in results if r['status']==200);assert times
        cohorts.append({'config':args.config,'concurrency':concurrency,'attempted':48,'successful':len(times),'rejected_503':48-len(times),'elapsed_s':duration,'successful_rps':len(times)/duration,'p50_ms':statistics.median(times),'p95_ms':times[__import__('math').ceil(.95*len(times))-1]})
    print(json.dumps({'records':rows,'cohorts':cohorts}))
if __name__=='__main__':main()
