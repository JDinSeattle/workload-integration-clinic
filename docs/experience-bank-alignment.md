# Experience Bank implementation map

Result provenance: owner-confirmed separate cloud-hosted test results. The README reproduces the current selected bullets. Commands below exercise this checkout; new outcomes must be recorded separately from those supplied results.

| Result | Implementation and regression evidence | Reproduce | Scope / source difference |
|---|---|---|---|
| 1 | [worker.py](../worker.py) · [tests/test_lifecycle.py](../tests/test_lifecycle.py) | `make test` | Sealed memfd binds the measured bytes to executed bytes. |
| 2 | [service.py](../service.py) · [scripts/validate.py](../scripts/validate.py) · [tests/test_lifecycle.py](../tests/test_lifecycle.py) | `make verify` | qualified profile has 8 HTTP slots and 2 compute slots; historical compact/throughput profiles remain available. |
| 3 | [compose.yaml](../compose.yaml) · [scripts/validate_containers.py](../scripts/validate_containers.py) | `make container-verify` | Default container profile uses 2 CPUs and 256 MiB; OOM probe is a separate client child. |
| 4 | [service.py](../service.py) · [worker.py](../worker.py) · [tests/test_lifecycle.py](../tests/test_lifecycle.py) | `make test` | Default Compose drain allowance is 2 seconds before worker termination. |
| 5 | [scripts/validate.py](../scripts/validate.py) · [scripts/validate_containers.py](../scripts/validate_containers.py) | `make verify evidence-check` | Local rerun counts do not replace the 288-request cloud outcome. |

## Measurement boundaries

- 288 is the offered count, not the success count: the campaign is 171 oracle-correct successes plus 117 explicit 503 overload rejections, and the rejections are the evidence for bounded admission, not failures removed to raise a success rate.
- Closed-loop clients wait for each response before sending the next request, so slow responses lower offered load; with no independent arrival-rate control, no real network and no long steady state, the run cannot support a production QPS or service-capacity promise.
- Hashing in place and then exec by path is insufficient because the path can be replaced between the two resolutions; the sealed memfd fixes the hashed object and the executed object to one immutable snapshot. This repairs identity consistency, not operator performance.
- The OOM probe kills a child in a separate client container and proves that cgroup limit; it does not demonstrate that the API restarts or recovers automatically after being OOM-killed.
- CPU and PID cgroup settings are observed; CPU fairness and PID exhaustion are not benchmarked.
- Local Ubuntu 24.04 / Docker Engine 27.5 lab with separate hosted CI, not a cloud deployment or production traffic; 10 regressions and 11 container checks are test counts, not capacity evidence.
- This work claims no before/after performance improvement.

## Local verification

See `docs/alignment-verification.json` for commands and outcomes from this checkout. Supplied cloud numbers, historical checked-in artifacts and new local checks are separate evidence sets. A skipped dependency test is not a pass.
