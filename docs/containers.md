# Container runtime qualification

The reference service now has a multi-stage container build, Compose deployment and an independent real-container acceptance campaign. The service retains loopback binding by default; the container command explicitly sets `--host 0.0.0.0`. Native tests and historical measurements remain separate.

## Run

Requirements: Linux amd64 Docker Engine, Compose with `--wait`, cgroup v2 and host Python 3.12+. Initial builds download pinned official Python images and Debian compiler packages. The runner fails if required cgroup evidence is unavailable; unsupported behavior is not silently skipped.

```bash
make container-verify
python3 evidence.py .runs/container
```

The runner uses a random `cc-workload-*` project and a dynamic port published only on host loopback. Bulk load originates in a separate client container on the dedicated bridge. It preserves every command outcome, HTTP cohort result, runtime probe and stop result, then removes only its own resources. It does not mount the daemon socket, use host networking, run privileged containers, or prune unrelated Docker data.

For manual use:

```bash
make container-up
docker compose port api 8080
docker compose run --rm client python container/client.py smoke
make container-down
```

Use the reported loopback port for `/health`, `/ready` or `/metrics`. Compose uses a normal dedicated bridge for host port publication. An initial internal-only network on the observed engine returned `invalid IP:0` instead of a usable published port; the harness now explicitly requires a real `127.0.0.1` port. B intentionally uses internal-only bridges because it publishes no host ports.

## Runtime and build decisions

- UID/GID 10001, all capabilities dropped, no-new-privileges, read-only root and a bounded `/tmp` tmpfs.
- One CPU quota, 256 MiB memory with no additional swap, and 64 PID limit. The runner checks cgroup files inside the actual container.
- A health check queries `/ready`. The Python entrypoint receives SIGTERM directly; Docker gives eight seconds before external forced kill. Application draining has its own shorter deadline.
- The worker still runs from a sealed memfd. Runtime packaging neither disables the default Docker seccomp profile nor bypasses the existing exact-byte worker identity check.
- Both stages pin Python 3.14.7's official Debian image digest. The build stage verifies vendored source and records the actual compiler/package inventory; the runtime has no compiler. Debian package resolution is not snapshot-pinned, so bit-for-bit rebuild identity across time is not promised. Each image/run records its actual worker SHA-256, which need not equal a binary built with the host's different compiler.

[Compose runtime configuration](https://docs.docker.com/reference/compose-file/services/) and [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/) motivated these checks. Setting a configuration field alone is not treated as runtime verification.

## Acceptance contracts

The load campaign sends 288 requests across compact/throughput configurations and concurrency 1/4/8. Every successful result must match the independently computable matrix oracle; 503 overload responses remain visible beside successful p50/p95 and throughput. It also runs compact → throughput → compact rollback with a consistent worker digest. Measurements are a local bounded workload, not production capacity or a before/after performance improvement.

Eleven explicit checks cover rollback, runtime hardening, invalid version/input/resource requests, memory enforcement, API health after a separate resource probe, graceful stop, forced drain, restoring the native image, and `docker stop` exiting cleanly.

The memory probe runs an allocating child in a fresh client container with the same memory cap. Success requires both child SIGKILL and an increment in that container's cgroup `memory.events` `oom_kill` counter. [An initial observation](failures/container-oom-observation.json) showed exit 137 with Docker `OOMKilled=false`; the harness therefore does not infer OOM from the exit code alone. This proves a separate container's memory enforcement, not automatic recovery of an OOM-killed API.

For deterministic in-flight stop tests, a **separate fixture image** contains a delayed 1×1 worker. The real HTTP service and its worker lifecycle remain unchanged. Tests confirm readiness becomes 503, new work rejects, an accepted result finishes during graceful drain, and a shorter deadline kills the delayed worker and returns 502 before the container exits zero. The fixture's sleep and artificial `kernel_us` are explicitly excluded from all performance results. Finally the native worker image is restored and actual GEMM succeeds again.

## Evidence and limitations

[Measured container results](container-results.md) and `evidence/containers-20260907/` retain raw HTTP data, cgroup counters, signals, compiler inventory, image identity and cleanup results. CI runs the same command on a hosted Ubuntu runner. Neither local containers nor hosted CI prove AWS deployment, IAM/VPC correctness, managed load-balancer behavior, cross-node availability or a production SLA. PID/CPU configuration is observed; CPU fairness and PID exhaustion are not benchmarked. No new kernel/HTTP speedup is claimed.
