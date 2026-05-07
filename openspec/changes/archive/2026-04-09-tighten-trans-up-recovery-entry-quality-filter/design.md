## Context

当前主线已经默认放松 `TRANS_UP` 恢复态 benchmark gate，这一步解决了“恢复态买不进去”的问题，但全样本差分显示新引入的恢复态仓位质量不够，主要以失败 breakout 和快速风险退出结束。现有 breakout provider 已经产出 `residual_strength_score` 与 `breakout_margin_score`，且 `BULL` 内已有 quality veto 先例，因此最小实现应该复用既有指标，在后处理旁路上单独加闸门。

## Goals / Non-Goals

**Goals:**
- 只对 `TRANS_UP + benchmark_off` 的恢复态旁路生效。
- 只复用现有 `residual_strength_score / breakout_margin_score`。
- 保留恢复态重建能力，同时削掉低质量恢复 entry。
- 输出明确 diagnostics，便于后续 A/B 归因。

**Non-Goals:**
- 不修改股票池。
- 不修改 `BULL` 内已有 breakout quality veto 逻辑。
- 不重写 provider 打分体系。
- 不改变 `pullback_only` 的准入规则。

## Decisions

### 1. 质量过滤放在 `signal_postprocess`，不回写 provider
- 选择：在恢复态 benchmark gate 旁路成立后，对 `buy_signals` 再做一次最小质量过滤。
- 原因：问题发生在恢复态旁路，不在 provider 原始候选生成阶段；把过滤放在后处理层最小、可回滚、可观察。
- 备选方案：
  - 直接扩展 provider 的 `bull_breakout_quality_veto` 到 `TRANS_UP`：会污染 `BULL` 与 `TRANS_UP` 的能力边界。
  - 新增独立 provider 评分：自由度太高，不符合当前最小改动原则。

### 2. 仅过滤 `breakout / pullback_overlap`
- 选择：与 `bull_breakout_quality_veto` 保持一致，不过滤 `pullback_only`。
- 原因：当前全样本拖累主要来自恢复态 breakout 失败，不需要额外扩大作用面。

### 3. 配置字段放在 `market_filter`
- 选择：恢复态 quality filter 作为 market filter 旁路的附属开关，放入 `market_filter`。
- 原因：它本质上是对 benchmark gate 放松后果的再约束，不是 ranking 主逻辑。
- 备选方案：放到 `signal_generation.ranking`。缺点是会让 `BULL veto` 与 `TRANS_UP recovery filter` 混在同一层，解释边界变差。

### 4. 增加独立 diagnostics 计数
- 选择：增加 `trans_up_recovery_quality_filter_*` diagnostics 字段。
- 原因：后续要判断恢复态变弱是“买得更多但买得差”，必须能直接看到被过滤掉多少。

## Risks / Trade-offs

- [风险] 阈值过严会再次把恢复态压死。 → 先默认关闭，只做 A/B，再决定是否提升默认值。
- [风险] 阈值过松则无法改善恢复态质量。 → 直接复用现有 `bull_breakout_quality_veto` 研究阈值，减少自由度。
- [风险] 后处理过滤可能与已有 state gate 混淆。 → 只在 `trans_up_recovery_gate_relaxed = true` 时生效，并写 diagnostics。

## Migration Plan

1. 新增 `market_filter` 配置字段与 schema/compiler/runner 编译链。
2. 在 `signal_postprocess` 中增加恢复态质量过滤。
3. 增加 route control 与 compiler 单测。
4. 用固定窗口做 stock-only 和 combo A/B。
5. 若 A/B 正向，再决定是否提升默认值。

## Open Questions

- 当前第一轮阈值是否直接复用 `0.94 / 0.55`，还是只先启用其中一个维度。
- 如果 stock-only 正向、combo 不正向，是否需要把该开关降为研究态而不是主线默认值。
