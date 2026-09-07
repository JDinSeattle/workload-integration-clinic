#!/usr/bin/env python3
"""Executable handoff diagnostics: local worker + live compatibility contract."""
import argparse, hashlib, json, os, pathlib, subprocess, urllib.request

def main():
    p=argparse.ArgumentParser(); p.add_argument('--binary',default='build/gemm'); p.add_argument('--url',default='http://127.0.0.1:8080'); a=p.parse_args()
    report={'checks':[]}; binary=pathlib.Path(a.binary)
    def add(name,ok,detail): report['checks'].append({'name':name,'pass':ok,'detail':detail})
    add('executable_permission',binary.is_file() and os.access(binary,os.X_OK),'run python3 scripts/install.py to rebuild project-owned worker')
    try:
        v=subprocess.run([str(binary.resolve()),'--version'],check=True,text=True,capture_output=True,timeout=3).stdout.strip()
        add('worker_protocol',v=='gemm-cpu-contract/1 fixed',v)
        with urllib.request.urlopen(a.url+'/health',timeout=3) as r: health=json.load(r)
        add('api_version',health['api_version']==1,health)
        add('deployment_digest',health['worker_sha256']==hashlib.sha256(binary.read_bytes()).hexdigest(),'restart service after worker replacement')
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as e: add('reachability_or_worker',False,str(e))
    print(json.dumps(report,indent=2)); return 0 if all(c['pass'] for c in report['checks']) else 1

if __name__=='__main__': raise SystemExit(main())
