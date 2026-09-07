# Simulated brief and handoff

This requirement brief is written by the author. No enterprise customer or independent user is represented.

## User objective and acceptance

A local analytics developer needs repeatable CPU matrix projections for small batches, wants to send actual matrix inputs rather than change benchmark source, and needs a safe rollback when offering more concurrency. Assume one Linux workstation, no new cloud spend, single local trust domain, and matrices no larger than 256 in each dimension. Hypothetical acceptance: 64³ requests at concurrency one have successful p95 below 100 ms, every successful result equals the independent business oracle, and overload is visible as rejection. Latency qualification is reported per measured cohort; CPU frequency and external host load are not controlled.

## Options and decision

| Option | Benefit | Cost / boundary | Decision basis |
|---|---|---|---|
| Direct CLI | lowest integration complexity | caller manages process/validation | retained for operator qualification |
| Compact HTTP | explicit schema and one active worker | overload rejected; process startup per request | simplest supported application integration |
| Throughput HTTP | four workers | more concurrent subprocess memory, Python parsing contention | compare six measured cohorts before choosing |
| Long-lived native server / BLAS | likely lower per-call overhead | larger implementation and numerical dependency scope | future experiment; no unmeasured speed claim |

No dollar savings are claimed. Existing workstation capital cost is sunk for this lab; four workers increase instantaneous resource use, and CPU-seconds/request would be needed for a billed deployment comparison. The chosen loop ordering improves contiguous B/C access, but HTTP p95 includes Python parsing, output validation and process startup, so the kernel ratio is not an endpoint speedup claim.

## Installation and business demo

```bash
python3 scripts/install.py
python3 scripts/install.py  # repeatable; no global environment edits
python3 service.py --config compact --port 8080 --log .runs/service.jsonl
```

In another terminal:

```bash
python3 scripts/doctor.py --url http://127.0.0.1:8080
curl --fail-with-body -sS http://127.0.0.1:8080/v1/gemm \
  -H 'Content-Type: application/json' \
  -d '{"api_version":1,"id":"demo-1","m":1,"n":1,"k":2,"a":[2,3],"b":[4,5]}'
```

Expected business output: `values: [23]`, matching `2*4+3*5`. The response also exposes the executed worker digest, which doctor compares with the local binary.

## Migration and rollback

Drain the local caller, stop the compact process with Ctrl-C, start the same binary with `--config throughput`, run doctor and the business request, then restart compact to roll back. This path incurs downtime. `make verify` automatically executes compact → throughput → compact and validates output at all three stages; `migration.json` is its record. No schema conversion is needed because both configurations use protocol 1. Keep the previous executable when changing an actual binary version; this lab tests configuration rollback only.

## Troubleshooting decisions

| Symptom / trigger | Executable check | Basis | Recovery |
|---|---|---|---|
| version 400 | send the demo with `api_version: 2` | only protocol 1 supported | use version 1 or deploy separately qualified adapter |
| resource 400 | set m=129 under compact | dimension > compact limit, checked before execution | choose throughput after qualification or reduce shape |
| input 400 | provide fewer than m*k A values | schema validation failure | correct matrix layout and count |
| permission 502 | `test -x build/gemm`; run doctor | worker cannot be executed | rerun project-local installer |
| worker 504 | inspect `faults.json` timeout fixture | parent deadline kills/reaps child | reduce workload, diagnose worker, requalify limits |
| overload 503 | inspect HTTP status counts, `capacity.json` | configured compute slots occupied | caller backoff / reduce concurrency; qualify throughput |
| digest doctor failure | compare health and `sha256sum build/gemm` | running server loaded different worker identity | restart service with intended verified binary |
| connection failure | doctor and listener log | process/port unavailable; >32 handlers outside tested envelope | restart on an unused loopback port; reduce offered load |

The automated permission/timeout fixtures affect test-owned executable copies only. `docs/failures/overload-before-fix.txt` captures the original early-close connection bug; the final load test requires all outcomes to be correct business responses or explicit 503, so it is a regression test for that fix.

## Author handoff audit

The validator runs the installer twice, runs doctor against each configuration, sends 288 capacity requests plus migration and fault traffic, validates answers, changes configuration and rolls back. This is **author self-test**, not another person's installation. No independent user time-to-deploy is claimed. Someone evaluating the repository can use the commands above and record their own time/blockers in a new evidence run.
