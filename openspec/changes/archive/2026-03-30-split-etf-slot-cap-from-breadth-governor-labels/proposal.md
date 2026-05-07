## Why

当前 formal ETF Phase 1 的 Governor 预算摘要把 ETF sleeve 的 `slot_cap` 压缩错误地标记成 `BREADTH_CAP_ACTIVE`，导致零交易诊断、审计摘要和日级快照无法区分“真实 breadth 生效”和“ETF 本地槽位上限生效”。这个误标已经污染根因解释，需要先修正标签合同，再决定是否调整 `TRANS_DOWN/RISK_OFF` 的策略口径。

## What Changes

- 拆分 Governor 预算摘要中的真实 breadth 限仓信号和 ETF sleeve slot-cap 限仓信号。
- 仅在 breadth 模块真实启用并且实际压缩仓位时输出 `BREADTH_CAP_ACTIVE`。
- 为 `cn_etf` sleeve 新增准确的 slot-cap 预算标签和最小来源字段，避免再把 ETF 约束误报成 breadth。
- 更新 ETF diagnostics、zero-trade diagnostics 和相关回归测试，保证新标签能被稳定消费。
- 不修改 `effective_max_positions`、`slot_cap`、`requested_budget` 或正式策略状态映射。

## Capabilities

### New Capabilities
- 无

### Modified Capabilities
- `cn-a-portfolio-governor`: Governor 预算证据链需要区分真实 breadth 限仓与 ETF sleeve slot-cap 限仓。
- `cn-etf-beta-sleeve`: ETF sleeve 需要向下游暴露 slot-cap 来源，供 Governor 和 diagnostics 正确标注。

## Impact

- 影响 `backend/core/config/cn_a_governed_mainline.py` 的 Governor 预算摘要合同。
- 影响 `backend/core/stage_pipeline/adapters/day_controls.py` 的控制面传递字段。
- 影响 `backend/core/engine_vector/cn_etf_beta_signal_provider.py` 暴露的 slot-cap 来源诊断。
- 影响 `backend/research/cn_etf_phase1_zero_trade_diagnostics.py` 和相关单测。
- 不改变正式 study、资产池、状态预算策略和交易行为。
