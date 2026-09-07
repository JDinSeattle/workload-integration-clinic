#!/usr/bin/env python3
"""Idempotent, hash-checked installation into this repo only; no global packages."""
import hashlib, json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]

def install():
    source=ROOT/'vendor/gemm.cpp'; lock=json.loads((ROOT/'vendor/lock.json').read_text())
    if hashlib.sha256(source.read_bytes()).hexdigest()!=lock['sha256']: raise ValueError('vendor source hash mismatch')
    (ROOT/'build').mkdir(exist_ok=True)
    target=ROOT/'build/gemm'; pending=ROOT/'build/gemm.pending'
    subprocess.run(['g++','-std=c++17','-O3','-Wall','-Wextra','-Werror',str(source),'-o',str(pending)],check=True)
    pending.replace(target)
    return target

if __name__=='__main__': print(install())
