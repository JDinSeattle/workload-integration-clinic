# Measured Docker results — 2026-09-07

Run completed 2026-09-07T23:36:55Z. Host: 13th Gen Intel(R) Core(TM) i9-13900K, Linux 7.0.0-29-generic; Docker 29.8.0, Compose 5.3.1, cgroup v2. Containers use digest-pinned Python 3.14.7 on Debian bookworm.

Single local Linux Docker Engine; other host activity was not controlled. Results are author-operated container evidence, not cloud service deployment or production capacity. CI repeats independently.

All **11 explicit checks passed**. The real HTTP campaign offered **288 requests**: **171** successful oracle-correct responses and **117** explicit overload rejections.

| Configuration | Concurrency | Success / attempted | 503 | Success RPS | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|
| compact | 1 | 48/48 | 0 | 66.00 | 9.91 | 56.57 |
| compact | 4 | 7/48 | 41 | 45.28 | 26.24 | 41.64 |
| compact | 8 | 8/48 | 40 | 6.99 | 35.04 | 1061.05 |
| throughput | 1 | 48/48 | 0 | 59.61 | 10.20 | 57.37 |
| throughput | 4 | 48/48 | 0 | 105.67 | 28.32 | 71.83 |
| throughput | 8 | 12/48 | 36 | 75.05 | 57.29 | 93.44 |

The separate 256 MiB client-container memory probe produced child return code -9 and a cgroup `oom_kill` increment of 1. Rootfs write returned EROFS; actual runtime UID was 10001, effective capabilities zero and NoNewPrivs enabled. Runtime CPU/memory/swap/PID values matched the declared limits.

graceful_stop: HTTP 200, container exit 0, observed signal-to-exit 1.304 s. The deterministic delayed worker is a separate fixture, excluded from performance data.
forced_drain: HTTP 502, container exit 0, observed signal-to-exit 0.694 s. The deterministic delayed worker is a separate fixture, excluded from performance data.

[Raw HTTP records](../evidence/containers-20260907/http.json) · [all checks](../evidence/containers-20260907/checks.json) · [hardening](../evidence/containers-20260907/hardening.json) · [compiler](../evidence/containers-20260907/compiler.json). Graceful shutdown can make a concurrent health probe fail as the service stops; the recorded container exit and accepted-request outcome determine this test result.

The 503 count must accompany successful latency. No native-versus-container speedup is claimed; host activity, compiler and process/network boundaries differ.

Both campaigns use scoped cleanup and confirmed their own containers, volumes and networks were removed. [Cleanup](../evidence/containers-20260907/cleanup.json) · [raw command journal](../evidence/containers-20260907/commands.jsonl) · [manifest](../evidence/containers-20260907/manifest.json). Historical native manifests retain their original source hashes.
