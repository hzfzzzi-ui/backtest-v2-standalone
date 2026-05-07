## Why

账户层已经成为 runtime 主真相，统一状态切换合同也已进入 `run_meta / audit / surface`，但 sleeves 的实际执行仍主要沿用旧的局部执行语义。当前最主要的双重语义残留，是账户层已经定义 `carry / de-risk / cash release / budget handoff`，而 ETF 与组合执行链还没有把这些 transition 动作作为正式执行输入消费。

## What Changes

- 新增账户层 transition contract 到执行层的正式消费能力，定义执行层必须消费账户层状态切换动作，而不是继续依赖局部 `RISK_OFF` patch 或旧 combo/ETF 弱势逻辑。
- 修改账户层 runtime cutover 合同，要求当 `runtime_truth_source = account_allocator` 时，执行链必须以账户层 transition runtime 作为主执行输入。
- 修改账户预算控制合同，要求预算控制不再停留在 steady-state budget，而要向执行层提供可消费的 transition action 集合。
- 修改 ETF 运行腿合同，要求 ETF 执行路径以账户层 transition action 为优先输入，旧 weak-state cash-drip / redeploy / materialization patch 只能作为 reference diagnostics，不得继续承接主语义。
- **BREAKING**：当账户层 transition runtime 可用时，旧的局部 weak-state 执行语义不再允许作为主执行真相。

## Capabilities

### New Capabilities
- `account-transition-execution-consumption`: 定义账户层状态切换动作如何被执行层正式消费，包括 carry、bounded de-risk、cash release 与 budget handoff 的执行输入合同。

### Modified Capabilities
- `account-allocation-runtime-cutover`: 将“账户层成为 runtime 主真相”扩展到执行输入层，要求执行层消费账户层 transition runtime。
- `account-budget-control`: 将预算控制从 steady-state 扩展到 transition action handoff，要求预算控制向执行层输出可消费动作。
- `cn-etf-beta-sleeve`: 将 ETF 运行腿从局部 weak-state patch 驱动改为账户层 transition action 优先消费。

## Impact

- Affected code:
  - `backend/core/services/account_allocator_shadow.py`
  - `backend/core/services/cn_stock_etf_unified_runtime_service.py`
  - `backend/core/engine_vector/etf_beta/*`
  - `backend/core/portfolio/*`
  - `backend/core/stage_pipeline/adapters/*`
  - `backend/core/audit/research_audit.py`
  - `backend/core/services/experiment_query_service.py`
  - `frontend/app/results-workbench/helpers/resultsFormatting.js`
- Affected systems:
  - account allocator runtime
  - ETF execution path
  - combo truth surface / audit / results-workbench
- Validation:
  - `A_STOCK_ETF_V1` 主回放
  - ETF standalone 回放
  - 最小正式回归
