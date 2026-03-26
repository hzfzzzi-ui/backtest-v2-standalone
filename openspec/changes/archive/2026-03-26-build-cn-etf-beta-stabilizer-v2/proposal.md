## Why

当前 `cn_etf_beta` 已具备独立研究与最小可交易能力，但从已完成的 `study-cn-etf-beta-rule-families` 可以确认：ETF sleeve 的实际问题不是“没有规则”，而是**作为 beta 稳定器时部署过轻、空仓过多、fallback 过于保守**。如果不先修正这三点，ETF 将继续表现为“轻仓战术轮动小仓”，而不是系统里应有的稳定 beta 层。

## What Changes

- 把 `cn_etf_beta` 从“单 ETF、强过滤、经常空仓”的研究式部署，调整为更符合 beta 稳定器角色的 V2 部署语义。
- 调整 ETF sleeve 的组合构建边界：
  - 从 `max_selected_symbols = 1` 扩展为允许小规模并持
  - 明确 beta 稳定器的候选池与持仓上限
- 调整 ETF sleeve 的 fallback 语义：
  - 不再默认把大部分风险关闭都落为纯现金
  - 引入正式防守 fallback 口径，并要求产物中可审计
- 调整 Governor 与 ETF sleeve 的预算语义：
  - 让 ETF 在 `RISK_ON / NEUTRAL` 下具备更合理的目标暴露
  - 避免继续把 ETF 压成接近不部署
- **BREAKING**：`cn_etf_beta` 的“beta 稳定器”定义从研究型小仓轮动，升级为受 Governor 管理的正式稳定 beta sleeve 语义。

## Capabilities

### New Capabilities

### Modified Capabilities

- `cn-etf-beta-sleeve`: ETF beta sleeve 的候选池、并持数、fallback、部署语义与研究验收口径将调整为稳定器模式。
- `cn-a-portfolio-governor`: Governor 对 ETF sleeve 的预算映射和 deployability 语义将调整，以匹配 beta 稳定器角色。
- `backtest-research-audit`: 研究审计将新增 ETF 稳定器部署是否真实生效的证据要求，包括 fallback、实际暴露和预算压缩来源。

## Impact

- Affected code:
  - `backend/core/config/cn_a_governed_mainline.py`
  - `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
  - `backend/core/stage_pipeline/adapters/day_controls.py`
  - `backend/core/stage_pipeline/adapters/order_planning.py`
  - `backend/core/portfolio/portfolio_runtime.py`
  - `backend/core/audit/research_audit.py`
  - `backend/api/backtest_v2/artifacts_finalize.py`
- Affected research entries:
  - `research/studies/etf/*`
- Affected artifacts:
  - `run_meta.json`
  - `audit.json`
  - `portfolio_daily.csv`
  - ETF 规则族 compare / summary 输出
