# Interview preparation / 面试准备

Target: Developer technology · solutions engineering.

Explain the code path and one retained failure before citing any metric. All numbers must link to the checked-in evidence and its hardware/software manifest. A GitHub CI pass demonstrates reproducibility, not production use.

可陈述：独立实现、真实本地测试、故障定位、可复现证据。不可陈述：企业客户、生产规模、未测硬件成绩、上游已合并贡献、独立用户验收。先按 README 完整复现，再练习解释每个边界和失败。

## Evidence-led talking points

- Start with the simulated brief, SLO and resource constraints, then show how each is represented in validation or an explicitly marked assumption.
- Demonstrate actual supplied matrices producing 23, rather than treating health HTTP 200 as business success.
- Explain the overload failure retained in the repository: unread request bodies can cause TCP resets. Separating bounded connection handling from compute admission makes tested overloads explicit 503 responses.
- Compare compact/throughput cohorts using success rate and successful p95 together. A lower successful p95 with many rejected requests is not an unconditional improvement.
- Compare gprof and kernel pairs with HTTP measurements. Faster GEMM is only one component of user latency; process startup and Python parsing remain.
- Run doctor, show a permission failure, and perform the documented rollback. Handoff validation is author-operated; another person's install time is not fabricated.

Resume wording, after reproducing: “Delivered a bounded CPU GEMM HTTP reference integration with two resource profiles, 288-request capacity matrix, five executable failure cases and configuration rollback; diagnosed an overload connection-reset bug and provided profiler evidence, deployment diagnostics and handoff documentation.” Do not call this GPU inference serving or external customer delivery.
