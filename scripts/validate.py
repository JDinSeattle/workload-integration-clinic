#!/usr/bin/env python3
import argparse, concurrent.futures, contextlib, cProfile, io, json, math, pathlib, pstats, random, statistics, subprocess, sys, threading, time, urllib.error, urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from evidence import command, digest, fresh, seal, write
from service import Server, validate_request, CONFIGS
from scripts.install import install

@contextlib.contextmanager
def running(binary,config,log):
    server=Server(('127.0.0.1',0),binary,config,log)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try: yield server, f'http://127.0.0.1:{server.server_port}'
    finally: server.shutdown(); server.server_close(); thread.join(timeout=5)

def request(url,body):
    start=time.monotonic_ns()
    data=json.dumps(body).encode()
    req=urllib.request.Request(url+'/v1/gemm',data,{'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=5) as r: status=r.status; raw=r.read()
    except urllib.error.HTTPError as e: status=e.code; raw=e.read()
    return {'status':status,'body':json.loads(raw) if raw else {},'e2e_ms':(time.monotonic_ns()-start)/1e6,'id':body.get('id')}

def case(size,identifier):
    # Rectangular real supplied input with hand-computable result: sum(A_row) * B constant.
    return {'api_version':1,'id':identifier,'m':size,'n':size,'k':size,
            'a':[float(i%5-2) for i in range(size*size)],'b':[.5]*(size*size)}

def correct(body,response):
    wanted=[sum(body['a'][i*body['k']:(i+1)*body['k']])*.5 for i in range(body['m']) for j in range(body['n'])]
    return response['status']==200 and response['body']['values']==wanted

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='.runs/latest'); args=ap.parse_args()
    out=fresh(ROOT,args.out); binary=install()
    sha=digest(binary); assert digest(install())==sha
    records=[]; summaries=[]; migration=[]
    for config in ['compact','throughput','compact']:
      with running(binary,config,out/'service.jsonl') as (server,url):
        (out/f'doctor-{config}.json').write_text(command([sys.executable,str(ROOT/'scripts/doctor.py'),'--binary',str(binary),'--url',url]))
        smoke=case(3,'migration-'+str(len(migration))); r=request(url,smoke)
        assert correct(smoke,r); migration.append({'config':config,'response':r})
        if len(migration)==3: continue
        for concurrency in [1,4,8]:
            start=time.monotonic()
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                bodies=[case(64,f'{config}-{concurrency}-{i}') for i in range(48)]
                rows=list(pool.map(lambda b:request(url,b),bodies))
            duration=time.monotonic()-start
            for b,r in zip(bodies,rows):
                assert r['status']==503 or correct(b,r)
                r.pop('body'); r.update(config=config,concurrency=concurrency); records.append(r)
            latency=sorted(r['e2e_ms'] for r in rows if r['status']==200)
            summaries.append({'config':config,'concurrency':concurrency,'attempted':len(rows),'business_success':len(latency),
                'rejected_503':sum(r['status']==503 for r in rows),'elapsed_s':duration,'successful_rps':len(latency)/duration,
                'p50_ms':statistics.median(latency) if latency else None,'p95_ms':latency[math.ceil(.95*len(latency))-1] if latency else None,
                'meets_hypothetical_latency_target':bool(latency) and latency[math.ceil(.95*len(latency))-1]<100})
    failures=[]
    with running(binary,'compact',out/'service.jsonl') as (server,url):
        for label,edit in [('version',{'api_version':2}),('resource',{'m':129}),('input',{'a':[]})]:
            b=case(2,label); b.update(edit); r=request(url,b); assert r['status']==400; failures.append({'fault':label,**r})
        # Permission denial applies to this test-owned copy, never the shared installed binary.
        blocked=out/'worker-no-exec'; blocked.write_bytes(binary.read_bytes()); blocked.chmod(0o600)
        server.binary=blocked; r=request(url,case(2,'permission')); assert r['status']==502; failures.append({'fault':'permission',**r})
        server.binary=binary; r=request(url,case(2,'recovered')); assert correct(case(2,'recovered'),r)
        blocked.unlink()
        sleeper=out/'sleeper'; sleeper.write_text('#!/bin/sh\nexec sleep 5\n'); sleeper.chmod(0o700)
        server.binary=sleeper; server.config['timeout']=.1
        r=request(url,case(2,'timeout')); assert r['status']==504; failures.append({'fault':'timeout',**r}); sleeper.unlink()
    # Native gprof gives actual code-level attribution in addition to timing evidence.
    profile_bin=ROOT/'build/gemm-profile'
    subprocess.run(['g++','-std=c++17','-O2','-pg','-fno-pie','-no-pie',str(ROOT/'vendor/gemm.cpp'),'-o',str(profile_bin)],check=True)
    for mode in ['reference','optimized']:
        command([str(profile_bin),mode,'128','128','128','200','7','generated'],cwd=out)
        (out/f'gprof-{mode}.txt').write_text(command(['gprof','--demangle',str(profile_bin),str(out/'gmon.out')]))
    (out/'gmon.out').unlink(missing_ok=True)
    # Paired kernel timings are kept distinct from HTTP latency (serialization/startup included).
    pairs=[]; rng=random.Random(947)
    for i in range(20):
        modes=['reference','optimized']; rng.shuffle(modes); row={'pair':i,'order':modes}
        for mode in modes:
            result=json.loads(command([str(binary),mode,'128','128','128','10','7','generated']))
            row[mode]=result['kernel_us']
        pairs.append(row)
    write(out/'capacity.json',summaries); write(out/'faults.json',failures); write(out/'migration.json',migration)
    write(out/'kernel-pairs.json',pairs)
    (out/'http.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    seal(ROOT,out,{'binary_sha256':sha,'compiler':command(['g++','--version']).splitlines()[0],
        'installer_repeated':True,'handoff':'author self-test; no independent customer/user',
        'SLO':'hypothetical brief: successful p95 <100 ms for 64^3 concurrency=1; overload explicitly rejected',
        'profile_limit':'gprof instrumented binary differs from O3 benchmark; sampling granularity may produce no samples for short optimized calls'})
    print(json.dumps({'capacity':summaries,'fault_cases':len(failures),'migration':'compact -> throughput -> compact passed'},indent=2))

if __name__=='__main__': main()
