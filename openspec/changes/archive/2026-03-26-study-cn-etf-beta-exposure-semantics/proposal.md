## Why

当前 `cn_etf_beta` 的主要问题已经从“规则不可交易”收敛为“暴露语义不合理”。最近两轮研究都显示，ETF sleeve 的收益差，主因不是买卖规则本身完全失效，而是 `target_exposure` 偏低、实际 deployability 长期不足、fallback 语义过于保守，导致这条 beta 稳定器长期只以很低仓位运行。

## What Changes

- 聚焦重做 `cn_etf_beta` 的暴露语义研究，不改 ETF 主候选池，不扩资产范围。
- 为 ETF sleeve 正式定义并研究：
  - `target_exposure`
  - `min_deployable_exposure`
  - `deployability`
  - `under_deploy_reason_codes`
- 把“ETF 稳定器是否真正部署起来”设为正式验收对象，而不再只看 CAGR。
- 研究并比较更合理的 ETF beta 暴露映射：
  - 固定目标暴露
  - 状态分段目标暴露
  - 不同的最小可部署阈值
- **BREAKING**：ETF sleeve 的下一轮主研究线将不再默认把“收益差”归因于候选池或买卖规则，而是优先归因于暴露语义和 Governor 部署约束。

## Capabilities

### New Capabilities
- `cn-etf-beta-exposure-semantics`: 定义 ETF beta 稳定器的目标暴露、最小可部署暴露、部署不足归因与最小 AB 研究框架。

### Modified Capabilities
- `cn-etf-beta-sleeve`: ETF beta sleeve 的正式研究重点从“可交易规则族”扩展到“暴露语义与稳定器部署行为”。
- `cn-a-portfolio-governor`: Governor 需要对 ETF sleeve 输出更可审计的目标暴露、部署不足与预算压缩语义。
- `backtest-research-audit`: 研究审计需要把 ETF sleeve 的实际部署强度、空仓损失来源、fallback 使用情况纳入正式 gate 证据。

## Impact

- Affected code:
  - `backend/core/config/cn_a_governed_mainline.py`
  - `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
  - `backend/core/stage_pipeline/adapters/day_controls.py`
  - `backend/core/stage_pipeline/adapters/daily_accounting.py`
  - `backend/core/audit/research_audit.py`
  - `backend/api/backtest_v2/artifacts_finalize.py`
- Affected research entries:
  - `research/studies/etf/*`
- Affected artifacts:
  - `run_meta.json`
  - `audit.json`
  - `portfolio_daily.csv`
  - `outputs/ops/*exposure*`
