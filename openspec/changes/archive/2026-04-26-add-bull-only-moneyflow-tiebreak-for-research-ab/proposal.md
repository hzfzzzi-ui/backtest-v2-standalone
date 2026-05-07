## Why

`monthly_divergence_rate` 在研究面上是正向候选因子，但前一轮把它接成日频 `veto` 后，当前股票腿基线明显变差。现有证据表明，这条因子更像 `BULL` 内部增强的中期 context 因子，而不是候选硬过滤器，因此需要一条最小、可审计的 `BULL-only tiebreak` A/B 来验证它是否适合作为弱上下文接入。

## What Changes

- 为 moneyflow overlay 增加研究态 `bull_only_tiebreak` 接法，只允许在 `BULL` 状态内参与候选并列打破，不改变主排序主干。
- 保持现有 `shadow`、`tiebreak`、`soft_weight`、`veto_bottom*` 语义不变，不修改 ETF / defense 或退出逻辑。
- 补充最小诊断字段，确保 A/B 能审计 `BULL-only` gating 是否真实生效。
- 基于当前股票腿基线运行严格 A/B，比较 baseline 与 `bull_only_tiebreak` 的绩效和行为差异。

## Capabilities

### New Capabilities
- `moneyflow-bull-only-tiebreak-overlay`: 为研究态 A/B 提供仅在 `BULL` 状态内启用的 moneyflow tiebreak overlay，并输出可审计诊断。

### Modified Capabilities
- None.

## Impact

- 影响代码：`backend/core/portfolio` 候选计划层，可能补充最小诊断字段；`tests/unit` 与 `tests/integration` 的候选计划验证。
- 影响系统：仅研究态 stock sleeve A/B；不改变正式主线默认行为。
- 影响产物：新增一组 A/B 输入与结果产物，用于比较 baseline 与 `bull_only_tiebreak`。
