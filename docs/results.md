# Measured local results

Execution date: 2026-09-07T21:47:29Z. 4 focused unit/regression tests passed, followed by the real integration campaign. See [validation log](../evidence/local/validation.log) and [manifest](../evidence/local/manifest.json).

CPU: 13th Gen Intel(R) Core(TM) i9-13900K. Kernel: 7.0.0-29-generic. All results are author-operated local measurements; cloud CI is a separate reproducibility check.

| Configuration | Concurrency | Success / attempted | 503 | Success RPS | p50 ms | p95 ms | Target <100 ms |
|---|---:|---:|---:|---:|---:|---:|---|
| compact | 1 | 48/48 | 0 | 114.64 | 8.67 | 9.44 | True |
| compact | 4 | 9/48 | 39 | 55.17 | 22.59 | 26.90 | True |
| compact | 8 | 9/48 | 39 | 48.78 | 38.05 | 46.41 | True |
| throughput | 1 | 48/48 | 0 | 93.36 | 8.33 | 19.67 | True |
| throughput | 4 | 48/48 | 0 | 193.24 | 18.24 | 27.41 | True |
| throughput | 8 | 31/48 | 17 | 126.67 | 39.98 | 75.89 | True |

288 offered requests across six closed-loop cohorts; all accepted results matched the business oracle. Five fault cases and compact → throughput → compact rollback passed. Paired optimized/reference kernel ratio: 0.3759 over 20 randomized pairs. This ratio does not describe endpoint latency.

[HTTP records](../evidence/local/http.jsonl) · [Faults](../evidence/local/faults.json) · [Migration](../evidence/local/migration.json) · [Reference gprof](../evidence/local/gprof-reference.txt) · [Optimized gprof](../evidence/local/gprof-optimized.txt) · [Handoff](brief-and-handoff.md)

An overloaded cohort may reject most requests; successful p95 must be read with acceptance rate. The 100 ms target is a hypothetical local requirement and does not imply an external SLA. Independent user handoff remains unverified.
