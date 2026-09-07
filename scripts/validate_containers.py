#!/usr/bin/env python3
"""Real container HTTP load, security/resource probes and Docker stop semantics."""
import argparse,concurrent.futures,json,pathlib,sys,time,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evidence import fresh,write,seal
from scripts.container_support import Stack
from scripts.validate import case,request,correct

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='.runs/container');args=ap.parse_args();out=fresh(ROOT,args.out)
    stack=Stack(ROOT,out,'cc-workload');write(out/'environment.json',stack.environment());checks=[];cohorts=[];records=[];migration=[]
    def url():
        address=stack.compose('port','api','8080').stdout.strip()
        assert address.startswith('127.0.0.1:') and int(address.rsplit(':',1)[1])>0,address
        return 'http://'+address
    def get(base,path):
        try:
            with urllib.request.urlopen(base+path,timeout=2) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:
            with e:return e.code,json.load(e)
    def up():stack.compose('up','--detach','--no-deps','--force-recreate','--wait','--wait-timeout','45','api',timeout=70)
    def record_check(name,**details):
        checks.append({'case':name,'passed':True,**details});write(out/'checks.json',checks)
    try:
        stack.compose('build','api',timeout=600)
        write(out/'resolved-compose.json',json.loads(stack.compose('config','--format','json').stdout))
        for index,config in enumerate(['compact','throughput','compact']):
            stack.env['CLINIC_CONFIG']=config;up();base=url();status,health=get(base,'/health');assert status==200 and health['config']==config
            body=case(3,'config-'+str(index));answer=request(base,body);assert correct(body,answer)
            migration.append({'config':config,'worker_sha256':health['worker_sha256'],'response':answer})
            if index==2:break
            load=json.loads(stack.compose('run','--rm','--no-deps','-T','client','python','container/client.py','load','--config',config,timeout=90).stdout)
            cohorts.extend(load['cohorts']);records.extend(load['records'])
        assert len({m['worker_sha256'] for m in migration})==1
        record_check('configuration_rollback',configurations=[m['config'] for m in migration])
        write(out/'migration.json',migration);write(out/'capacity.json',cohorts);write(out/'http.json',records)
        actual=json.loads(stack.execute('api','python','container/client.py','hardening').stdout)
        quota,period=map(int,actual['cgroup']['cpu.max'].split());assert quota/period==1
        assert int(actual['cgroup']['memory.max'])==256*1024*1024 and actual['cgroup']['memory.swap.max']=='0' and actual['cgroup']['pids.max']=='64'
        write(out/'hardening.json',actual);write(out/'container.json',stack.inspect_summary('api'))
        record_check('nonroot_readonly_no_capabilities_cgroup_limits',observed=actual)
        compiler=stack.execute('api','python','-c','import json,pathlib; print(json.dumps({p.name:p.read_text() for p in pathlib.Path("build").glob("*.txt")}))')
        write(out/'compiler.json',json.loads(compiler.stdout))
        base=url()
        for name,edit in [('version',{'api_version':2}),('input',{'a':[]}),('resource',{'m':129})]:
            body=case(2,name);body.update(edit);r=request(base,body);assert r['status']==400;record_check('invalid_'+name,status=r['status'])
        # A supervised child plus cgroup counters distinguishes OOM from arbitrary SIGKILL.
        probe=json.loads(stack.compose('run','--rm','--no-deps','-T','client','python','container/client.py','memory-probe',timeout=25).stdout)
        assert probe['oom_kill_delta']>0 and probe['child_returncode']==-9
        record_check('memory_limit_oom',observed=probe)
        smoke=case(2,'after-oom');assert correct(smoke,request(base,smoke));record_check('service_healthy_after_separate_container_oom')
        stack.files=['compose.yaml','container/compose.faults.yaml'];stack.compose('build','api',timeout=600)
        body={'api_version':1,'id':'drain','m':1,'n':1,'k':1,'a':[2],'b':[3]}
        for name,delay,drain,expected in [('graceful_stop','1','3',200),('forced_drain','30','0.1',502)]:
            stack.env.update(FIXTURE_SLEEP=delay,FIXTURE_DRAIN=drain);up();base=url();cid=stack.cid('api')
            with concurrent.futures.ThreadPoolExecutor(1) as pool:
                f=pool.submit(request,base,body);end=time.monotonic()+2
                while time.monotonic()<end:
                    if get(base,'/metrics')[1]['active']==1:break
                    time.sleep(.01)
                else:raise AssertionError('fixture request not admitted')
                # SIGTERM is sent through Docker to the actual container entrypoint.
                start=time.monotonic();stack.run(['docker','kill','--signal','SIGTERM',cid])
                if name=='graceful_stop':
                    assert get(base,'/ready')[0]==503
                    rejected=request(base,body);assert rejected['status']==503
                result=f.result(timeout=5);assert result['status']==expected,result
                if expected==200:assert result['body']['values']==[6.0]
                stack.run(['docker','wait',cid],timeout=8);elapsed=time.monotonic()-start
            stopped=stack.inspect('api')['State'];assert stopped['ExitCode']==0 and not stopped['OOMKilled'] and elapsed<8
            record_check(name,status=result['status'],elapsed_s=elapsed,state=stopped,fixture='test-owned delayed 1x1 worker; not a kernel performance sample')
        stack.files=['compose.yaml'];stack.env['CLINIC_CONFIG']='compact';up();base=url()
        recovery=case(3,'final-native-worker');assert correct(recovery,request(base,recovery));record_check('native_image_restored_after_fault_fixture')
        # Exercise docker stop itself on the real native service, not only kill --signal.
        cid=stack.cid('api');stack.run(['docker','stop','--timeout','8',cid],timeout=12);assert stack.inspect('api')['State']['ExitCode']==0
        record_check('docker_stop_native_exit_zero')
        write(out/'checks.json',checks);write(out/'summary.json',{'checks':len(checks),'all_expected':True,'offered_requests':len(records),'cohorts':len(cohorts),'successful_requests':sum(r['status']==200 for r in records),'rejected_503':sum(r['status']==503 for r in records),'performance_claim':None})
        print(json.dumps({'checks':len(checks),'offered_requests':len(records),'all_expected':True}),flush=True)
    finally:
        try:stack.close()
        finally:
            write(out/'cleanup.json',{'project':stack.project,'owned_resources_removed':stack.closed})
            seal(ROOT,out,{'execution':'Docker containers on local Linux CPU host','environment_file':'environment.json','cloud_deployment':False,'fault_fixture':'separate image; sleep is not GEMM performance'})
if __name__=='__main__':main()
