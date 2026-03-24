## Why

当前 A 股系统已经把 `market_regime_engine` 视为上游总控输入，但真实实现仍分散在 evaluator、weekly engine、audit 和产物拼装层之间，状态语义、解释字段和人工覆盖留痕还没有完全收口成一个正式 contract。现在需要先把它做成“可归因、可审计、可被 Governor 稳定消费”的正式模块，再继续推进 ETF beta、保险层和更复杂的仓位总控。

## What Changes

- 将 `market_regime_engine` 的正式输出统一到 canonical 五状态语义，明确 `base_state_5 / effective_state_5 / coarse_state / effective_coarse_state` 的 contract。
- 将“五状态是唯一正式状态真相源、三状态只做派生视图”写成硬约束，禁止下游再把三状态反向当成上游真相。
- 统一 `trend / risk / breadth / participation` 四类 block 评分与 `technical / sentiment / macro_global` 三类解释域的映射，要求状态输出同时携带 block 级与 domain 级归因。
- 补齐正式 `reason_codes`、`state_stability_metrics`、`feature_availability`、`manual_override` 结构，禁止人工覆盖静默改写原始状态。
- 让 `cn-a-portfolio-governor` 只消费一套正式 regime payload，不再依赖下游自行猜测状态语义或 fallback 含义。
- 让 `cn-a-attribution-audit` 和研究审计正式记录 regime 的 base/effective 状态、切换原因、低置信度抑制和 override 留痕。
- **BREAKING**: A 股系统正式对外状态语言只认 canonical 五状态，不再允许不同 engine 继续直接暴露各自私有状态名。
- **BREAKING**: `coarse_state / effective_coarse_state` 只允许作为派生视图存在，不再允许任何模块仅凭三状态重建或覆盖正式五状态。
- **BREAKING**: `manual_override` 必须保留 `base_*` 原始状态和 `effective_*` 生效状态的双轨输出，不再允许只输出最终状态。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `market-regime-framework`: 将市场状态框架从“可审计要求”推进到“统一 canonical 五状态、block/domain 归因、override 双轨留痕”的正式 contract。
- `cn-a-portfolio-governor`: 要求 Governor 只消费正式 regime payload，并明确 `risk_budget_multiplier / defense_bias / override` 的上游语义。
- `cn-a-attribution-audit`: 要求归因模块正式记录 regime 的 base/effective 状态、切换原因、state stability 和人工干预留痕。
- `backtest-research-audit`: 要求研究审计将 regime contract 合规性纳入正式检查，而不是只统计状态天数和切换次数。
- `results-workbench-snapshot-boundary`: 要求结果快照能暴露 regime 的核心解释字段，支持后续前端展示 Governor/Regime/Attribution 关系。

## Impact

- 影响后端：
  - `backend/core/engine_vector`
  - `backend/core/audit`
  - `backend/core/config`
  - `backend/core/stage_pipeline/adapters`
  - `backend/core/tools`
- 影响产物：
  - `portfolio_daily.csv`
  - `run_meta.json`
  - `audit.json`
  - regime / attribution debug 摘要
- 影响前端：
  - results workbench 的 snapshot 字段边界
- 不影响：
  - A 股股票 `V2 canonical` 数据口径
  - 当前 `cn_etf` 独立真值表
  - `value_bluechip_satellite` 与 `insurance_overlay` 的实现范围
