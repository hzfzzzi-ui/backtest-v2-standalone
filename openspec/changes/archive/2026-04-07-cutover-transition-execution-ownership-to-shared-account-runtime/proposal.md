## Why

当前账户层已经成为 runtime 主真相，但 transition execution 的真实 owner 仍然留在旧 ETF 单腿执行链里。这导致账户层合同、审计与前端解释已经切换，而真实执行仍由 `state_edge_cash_release`、`riskoff_cash_drip_topup` 等旧路径主导，持续制造双重语义。

## What Changes

- 新增共享账户执行 runtime，由账户层统一消费 `state_transition_runtime` 与 `transition_action_handoff`，直接生成 transition execution plan。
- **BREAKING** 当 `runtime_truth_source = account_allocator` 时，旧 ETF weak-state 执行路径不再拥有主执行结论，只允许作为 diagnostics/reference 输出。
- 把 `risk_on -> defensive` 作为第一优先实现族，要求执行 owner、reason code、reject reason 都来自账户层共享执行 runtime。
- 统一 `run_meta / audit / query / front-end` 对 transition execution 的主叙事，禁止再把 combo/reference 或 ETF 旧局部路径平铺成同级真相。
- 明确独立 sleeve 结果与共享账户执行 runtime 的边界：独立 sleeve 可继续产出研究/参考信息，但不得再反向决定账户层 transition owner。

## Capabilities

### New Capabilities
- `shared-account-transition-execution-runtime`: 定义共享账户执行 runtime 如何消费账户层状态切换合同，并成为 transition execution 的唯一 owner。

### Modified Capabilities
- `account-allocation-runtime-cutover`: 收紧 runtime 真相边界，要求账户层 transition execution 成为主执行结论来源。
- `account-budget-control`: 将 budget handoff 从解释层要求提升为共享执行 runtime 必须消费的正式合同。
- `cn-etf-beta-sleeve`: 旧 weak-state 执行路径降级为 diagnostics/reference，不再作为账户层 transition execution 的 owner。

## Impact

- 受影响代码主要在 `backend/core/services`、`backend/core/engine_vector/etf_beta`、`backend/core/portfolio`、`backend/core/stage_pipeline/adapters`、`backend/core/audit`、`backend/core/services/experiment_query_service.py`、`frontend/app/results-workbench/helpers`。
- 主影响面是 runtime 行为、审计证据、结果查询与前端解释，不涉及新增外部依赖。
- 这是 L3 行为级改动，回放与最小正式回归必须作为验收门槛。
