"""Scoped Docker Compose orchestration; no daemon socket enters a container."""
import json,os,pathlib,subprocess,time,uuid

class Stack:
    def __init__(self,root,out,prefix):
        self.root=pathlib.Path(root);self.out=pathlib.Path(out);self.project=prefix+'-'+uuid.uuid4().hex[:12]
        self.env=dict(os.environ,COMPOSE_PROJECT_NAME=self.project,COMPOSE_PROGRESS='plain',COMPOSE_ANSI='never')
        self.files=['compose.yaml'];self.sequence=0;self.closed=False
    def run(self,args,timeout=60,check=True):
        self.sequence+=1;start=time.monotonic()
        try:
            p=subprocess.run(args,cwd=self.root,env=self.env,capture_output=True,text=True,timeout=timeout)
            record={'argv':args,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'elapsed_s':time.monotonic()-start}
        except subprocess.TimeoutExpired as e:
            record={'argv':args,'timeout_s':timeout,'elapsed_s':time.monotonic()-start,'stdout':str(e.stdout or ''),'stderr':str(e.stderr or '')}
            self.record(record);raise
        self.record(record)
        if check and p.returncode:raise RuntimeError(f'{args[:5]} failed ({p.returncode}): {p.stderr[-1800:]}')
        return p
    def record(self,row):
        with (self.out/'commands.jsonl').open('a') as f:f.write(json.dumps(dict(sequence=self.sequence,**row))+'\n')
    def compose(self,*args,**kw):
        cmd=['docker','compose','--project-name',self.project]
        for f in self.files:cmd+=['-f',f]
        return self.run(cmd+list(args),**kw)
    def cid(self,service):
        value=self.compose('ps','--all','--quiet',service).stdout.strip();assert value and '\n' not in value,value
        return value
    def inspect(self,service):return json.loads(self.run(['docker','inspect',self.cid(service)]).stdout)[0]
    def inspect_summary(self,service):
        i=self.inspect(service);h=i['HostConfig'];c=i['Config']
        return {'id':i['Id'],'image_id':i['Image'],'user':c['User'],'entrypoint':c['Entrypoint'],'cmd':c['Cmd'],
            'readonly_rootfs':h['ReadonlyRootfs'],'privileged':h['Privileged'],'cap_drop':h['CapDrop'],'security_opt':h['SecurityOpt'],
            'nano_cpus':h['NanoCpus'],'memory_bytes':h['Memory'],'memory_swap_bytes':h['MemorySwap'],'pids_limit':h['PidsLimit'],
            'health':i['State'].get('Health'),'state':i['State'],'mounts':i['Mounts'],'networks':i['NetworkSettings']['Networks']}
    def execute(self,service,*args,**kw):return self.compose('exec','-T',service,*args,**kw)
    def wait_health(self,service,timeout=40):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            i=self.inspect(service)
            if i['State'].get('Health',{}).get('Status')=='healthy':return
            if not i['State']['Running']:raise RuntimeError('service exited: '+service)
            time.sleep(.2)
        raise TimeoutError('container health: '+service)
    def owned_network(self,suffix):
        name=self.project+'_'+suffix
        labels=json.loads(self.run(['docker','network','inspect',name]).stdout)[0]['Labels']
        assert labels['com.docker.compose.project']==self.project
        return name
    def close(self):
        if self.closed:return
        self.compose('logs','--no-color',timeout=30,check=False)
        result=self.compose('down','--volumes','--remove-orphans',timeout=60,check=False)
        if result.returncode:raise RuntimeError('scoped Compose cleanup failed')
        for kind,flag in [('container','-aq'),('network','-q'),('volume','-q')]:
            remain=self.run(['docker',kind,'ls',flag,'--filter','label=com.docker.compose.project='+self.project]).stdout.strip()
            assert not remain,'owned resource leaked: '+kind+' '+remain
        for suffix in ['runtime','fixture','collector']:
            self.run(['docker','image','rm',self.project+'-'+suffix],check=False)
        self.closed=True
    def environment(self):
        return {'project':self.project,'docker':json.loads(self.run(['docker','version','--format','{{json .}}']).stdout),
            'compose':self.run(['docker','compose','version','--short']).stdout.strip(),
            'host':json.loads(self.run(['docker','info','--format','{"os":{{json .OperatingSystem}},"kernel":{{json .KernelVersion}},"cgroup_version":{{json .CgroupVersion}},"cpus":{{.NCPU}}}']).stdout),
            'scope':'local Docker Engine; test-owned bridge networks, volumes and containers; not cloud service deployment'}
