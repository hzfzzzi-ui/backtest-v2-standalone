## Why

当前 `RISK_OFF` 的账户层左侧累积预算语义已经成为 runtime 主解释，但实际持仓行为没有变化。现在需要把“账户层预算成立”推进到“账户层预算能触发真实执行落地”，否则账户层预算仍停留在解释层而非行为层。

## What Changes

- 在 `RISK_OFF` 下新增账户层预算到执行意图的 materialization 合同，使 defense / core beta 预算缺口能够进入正式执行链。
- 将 `RISK_OFF` 下的账户层预算从“解释性目标”升级为“可触发部分去风险、释放现金、再分配买入”的正式运行语义。
- 保持 `TRANS_DOWN`、`stock alpha`、`50/50 reference`、总暴露上限和现有主 regime 定义不变。
- 为 explain / audit 增加账户层预算 materialization 的可观测字段和 reject 原因归因。

## Capabilities

### New Capabilities
- `riskoff-account-budget-execution-materialization`: 定义 `RISK_OFF` 下账户层预算如何触发部分去风险、释放现金并 materialize 为真实执行的正式合同。

### Modified Capabilities
- `account-allocation-runtime-cutover`: 将 `RISK_OFF` 下 runtime 从“账户层预算只负责解释”更新为“账户层预算可触发真实执行落地”。

## Impact

- Affected code:
  - `backend/core/services/cn_stock_etf_unified_runtime_service.py`
  - `backend/core/engine_vector/etf_beta/execution_paths.py`
  - `backend/core/portfolio/candidate_plan.py`
  - `backend/core/stage_pipeline/adapters/day_controls.py`
  - `backend/core/stage_pipeline/adapters/etf_beta_accounting.py`
  - `backend/core/audit/research_audit.py`
- Affected artifacts:
  - `run_meta.json`
  - `audit.json`
  - `portfolio_daily.csv`
  - ETF / unified combo reason codes
- Dependencies:
  - 依赖当前 `account_allocator_runtime` 已成为主真相
  - 依赖 `RISK_OFF` 左侧累积预算语义已成立
