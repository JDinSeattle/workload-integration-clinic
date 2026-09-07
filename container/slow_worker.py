#!/usr/local/bin/python3
"""Explicit test fixture: controlled delay, only the known 1x1 request contract."""
import json,os,sys,time
if sys.argv[1:]==['--version']:
    print('gemm-cpu-contract/1 fixed');raise SystemExit(0)
assert sys.argv[1:]==['optimized','1','1','1','1','0','stdin']
values=list(map(float,sys.stdin.read().split()));assert len(values)==2
# Marker is test-only and lives on the container's writable tmpfs.
open('/tmp/worker-started','w').write(str(os.getpid()))
time.sleep(float(os.environ['FIXTURE_SLEEP']))
print(json.dumps({'protocol':1,'values':[values[0]*values[1]],'kernel_us':[1]}))
