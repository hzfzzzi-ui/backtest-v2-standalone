## Why

当前结构重构已经完成，问题不再是谁是主真相，而是 ETF 腿在很多阶段仍然更像“按弱势触发的辅助腿”。如果目标是让 ETF 与 A 股个股腿错开风险收益，下一步更值得研究的是 ETF sleeve 全程非零持仓，并在 `defense / core_beta` 之间按状态切换，而不是继续围绕局部 weak-state patch 打转。

## What Changes

- 新增一条研究能力：ETF sleeve 尽量全程保持非零持仓，并按状态在 `defense / core_beta` 之间切换
- 在账户层预算合同中明确 ETF sleeve 的 always-on 研究语义，避免把 ETF 再做成第二条股票腿
- 在共享账户执行 runtime 中增加 always-on ETF 风险分层解释，明确 ETF 与 A 股个股腿的风险分工
- 补充最小 A/B 研究任务，重点比较 ETF 非零持仓率、ETF 与个股腿相关性、组合风险收益变化

## Capabilities

### New Capabilities
- `always-invested-etf-sleeve-state-separated-risk`: ETF sleeve 全程非零持仓、按状态在 `defense / core_beta` 间切换的研究能力

### Modified Capabilities
- `cn-etf-beta-sleeve`: ETF sleeve 增加 always-on 研究语义与状态分层风险定义
- `account-budget-control`: 账户层预算控制增加 ETF always-on 风险分层预算语义
- `shared-account-transition-execution-runtime`: 共享账户执行 runtime 增加 ETF always-on 风险分层 explain

## Impact

- `backend/core/services/account_allocator_shadow.py`
- `backend/core/services/cn_stock_etf_unified_runtime_service.py`
- `backend/core/engine_vector/etf_beta/*`
- `backend/core/audit/research_audit.py`
- `frontend/app/results-workbench/helpers/resultsFormatting.js`
- `openspec/specs/cn-etf-beta-sleeve`
- `openspec/specs/account-budget-control`
- `openspec/specs/shared-account-transition-execution-runtime`
