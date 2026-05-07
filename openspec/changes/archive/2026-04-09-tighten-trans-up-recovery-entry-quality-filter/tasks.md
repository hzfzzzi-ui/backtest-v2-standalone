## 1. OpenSpec 与配置链路

- [x] 1.1 补齐 proposal/design/specs，定义 `TRANS_UP` 恢复态质量过滤的能力边界。DoD：change 到 `apply-ready`；验证：`openspec status --change tighten-trans-up-recovery-entry-quality-filter`；风险：能力边界定义不清会污染既有 `BULL veto`。
- [x] 1.2 在 `models/schema/compiler/runner` 中新增恢复态质量过滤字段，默认关闭。DoD：字段能从 semantic config 编译到 runtime market_filter；验证：focused unit tests；风险：字段落不到 runtime 会导致 A/B 假阴性。

## 2. 恢复态后处理实现

- [x] 2.1 在 `signal_postprocess.py` 中实现只作用于 `TRANS_UP + benchmark_off` 的质量过滤，且仅过滤 `breakout / pullback_overlap`。DoD：低质量恢复态 entry 被拦截，高质量与 `pullback_only` 不受影响；验证：route control unit tests；风险：阈值逻辑误伤恢复态正常仓位。
- [x] 2.2 增加恢复态质量过滤 diagnostics 默认字段与计数。DoD：day_signals diagnostics 稳定包含应用标记和阻断计数；验证：unit tests；风险：缺少可观测性会导致后续无法归因。

## 3. 最小 A/B 研究

- [x] 3.1 跑 `2018-2022` stock-only A/B，判断恢复态 quality filter 是否改善 `TRANS_UP` 质量。DoD：产出基线/实验 exp_id 与核心指标；验证：perf + state diagnostics；风险：仅靠单窗口得出过强结论。
- [x] 3.2 跑 `2023-2026` stock-only 与 combo A/B，确认不会显著恶化当前窗口。DoD：产出组合与单腿对照；验证：perf + stock/ETF corr；风险：局部正向但组合负向。

## 4. 研究结论

- [x] 4.1 记录本轮结论：直接复用 `bull_breakout_quality_veto` 的 `0.94 / 0.55` 阈值作为 `TRANS_UP` 恢复态质量过滤，不值得推进为主线默认值。DoD：结果已回填；验证：stock-only 与 combo A/B 结果一致指向 no-go；风险：如果忽略 replay 口径差异，可能误判为逻辑错误而不是阈值不适配。
