## Why

当前系统已经把账户层预算与状态切换合同提升为主 runtime 真相，但真实执行仍由旧的 ETF weak-state 路径主导，导致 `run_meta/audit/front-end` 与实际拒绝原因长期分叉。现在必须完成执行 ownership 的硬切换，否则账户层只会继续停留在解释层，无法成为真正的配置中枢。

## What Changes

- 新增账户层 transition execution owner capability，定义当 `runtime_truth_source = account_allocator` 且存在 `transition_action_handoff` 时，执行层只能消费账户层 handoff。
- **BREAKING**：旧 `state_edge_cash_release`、`riskoff_cash_drip_topup`、`riskoff_account_budget_materialization`、`weak_state_inter_rebalance_defense_redeploy` 不再有资格产出主执行结论，只能降为 diagnostics/reference。
- 修改账户层 budget/runtime 合同，增加 `transition_execution_owner`、`transition_execution_status`、`transition_execution_reject_reason` 等正式字段。
- 修改 ETF 执行路径、day controls、candidate plan、accounting，使 `risk_on -> defensive` 的去风险、现金释放、budget handoff 由账户层 transition controller 主导。
- 修改 audit/query/front-end 主叙事，要求账户层 execution consumption 成为唯一主解释，旧 combo/weak-state 只允许进入 reference 区。

## Capabilities

### New Capabilities
- `account-transition-execution-ownership`: 规定账户层状态切换合同如何成为执行层唯一 owner，并定义消费状态、拒绝原因与 diagnostics/reference 边界。

### Modified Capabilities
- `account-allocation-runtime-cutover`: 从“账户层是主 runtime 真相”推进到“账户层也是主 transition execution 真相”。
- `account-budget-control`: 增加 transition execution owner 与 execution status 的正式字段和优先级约束。
- `cn-etf-beta-sleeve`: 弱势与状态切换执行必须消费账户层 handoff，旧 weak-state 执行逻辑降为参考诊断。

## Impact

- 影响代码：
  - `backend/core/services/account_allocator_shadow.py`
  - `backend/core/services/cn_stock_etf_unified_runtime_service.py`
  - `backend/core/engine_vector/etf_beta/execution_paths.py`
  - `backend/core/portfolio/candidate_plan.py`
  - `backend/core/stage_pipeline/adapters/day_controls.py`
  - `backend/core/stage_pipeline/adapters/etf_beta_accounting.py`
  - `backend/core/audit/research_audit.py`
  - `backend/core/services/experiment_query_service.py`
  - `frontend/app/results-workbench/helpers/resultsFormatting.js`
- 影响产物：
  - `run_meta.json`
  - `audit.json`
  - `surface/combo_truth`
- 影响系统：
  - 账户层 transition controller
  - ETF 执行链 owner 切换
  - 前端主解释与 diagnostics/reference 分区
