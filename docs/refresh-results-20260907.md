# Maintenance validation — 2026-09-07

**10 focused tests passed**, followed by the real integration campaign. [Raw log](../evidence/refresh-20260907/validation.log) · [manifest](../evidence/refresh-20260907/manifest.json).

Run: 2026-09-07T22:43:13Z; Python 3.14.4, 13th Gen Intel(R) Core(TM) i9-13900K, Linux 7.0.0-29-generic. Single author-operated Linux CPU host. Hosted CI execution is separate.

**288** HTTP requests across six closed-loop cohorts. All successful responses matched the independent business oracle; overload rejection remains visible. Five faults and compact → throughput → compact rollback passed. Six new lifecycle tests cover replacement/sealing, graceful/forced drain, timeout, invalid output and real CLI SIGTERM.

| Config | Concurrency | Success/attempted | 503 | Successful RPS | p95 ms |
|---|---:|---:|---:|---:|---:|
| compact | 1 | 48/48 | 0 | 104.31 | 15.57 |
| compact | 4 | 9/48 | 39 | 63.35 | 26.29 |
| compact | 8 | 6/48 | 42 | 41.94 | 48.84 |
| throughput | 1 | 48/48 | 0 | 133.28 | 9.40 |
| throughput | 4 | 48/48 | 0 | 149.03 | 39.21 |
| throughput | 8 | 15/48 | 33 | 88.35 | 74.52 |

These are host-specific observations, not a before/after service speedup or external SLA. The 100 ms target is hypothetical. Native gprof files and 20 kernel pairs remain separate from endpoint latency. Permission failure now rejects at startup snapshot construction; replacing path permissions after startup does not alter the sealed executable.

[HTTP records](../evidence/refresh-20260907/http.jsonl) · [capacity](../evidence/refresh-20260907/capacity.json) · [faults](../evidence/refresh-20260907/faults.json) · [migration](../evidence/refresh-20260907/migration.json)
