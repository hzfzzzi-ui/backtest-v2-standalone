## Why

当前账户层已经接管稳态预算，但状态切换、库存重构、现金释放和前端主叙事仍然部分停留在旧的 combo/ETF 局部语义里，导致账户层与执行层持续双重语义并存。现在需要补上统一的账户层状态切换合同，把 `risk_on -> defensive`、`defensive -> defensive`、`defensive -> recovery` 等切换规则上收到账户层，避免继续用 `RISK_OFF-only` 补丁推进。

## What Changes

- 新增账户层统一状态切换合同，覆盖全部状态切换类别，明确 carry、de-risk、cash release、budget handoff 的正式语义。
- 修改账户层 runtime cutover 要求，使账户层不仅负责稳态预算，也负责状态切换时的库存重构与执行意图输出。
- 修改账户层架构要求，明确账户状态机是上游真相，不再由 sleeve 状态聚合反推账户状态。
- **BREAKING** 收紧 combo/reference 的角色边界：旧 combo 只能作为 benchmark/reference 区存在，不得再与账户层主叙事并列承担 runtime 主真相。
- **BREAKING** 收紧结果查询与前端展示要求：当 `runtime_truth_source = account_allocator` 时，前端和查询层必须以账户层为唯一主叙事，旧 combo/governor 只允许作为参考说明出现。

## Capabilities

### New Capabilities
- `account-layer-state-transition-policy`: 定义账户层统一状态切换合同，覆盖不同状态切换类型下的库存重构、现金释放和预算移交语义。

### Modified Capabilities
- `account-allocation-architecture`: 账户层架构要求升级，明确账户状态机和状态切换合同是上游真相，sleeve 仅消费账户层输出。
- `account-allocation-runtime-cutover`: runtime cutover 要求升级，账户层必须输出状态切换执行意图，并收紧 combo/reference 的主真相边界。
- `account-budget-control`: 预算控制要求升级，从稳态预算扩展到账户层状态切换时的 budget handoff 与 carry/de-risk 规则。

## Impact

- 影响代码：`backend/core/services/account_allocator_shadow.py`、`backend/core/services/cn_stock_etf_unified_runtime_service.py`、`backend/core/engine_vector/etf_beta/execution_paths.py`、`backend/core/stage_pipeline/adapters/day_controls.py`、`backend/core/portfolio/candidate_plan.py`、`backend/core/audit/research_audit.py`、`backend/core/services/experiment_query_service.py`、`frontend/app/results-workbench/helpers/resultsFormatting.js`。
- 影响系统：账户层 runtime、combo/reference 边界、query/surface、前端 governor/account allocator 展示。
- 影响研究方法：后续状态切换研究必须以账户层统一合同为入口，不再接受 `RISK_OFF-only` 局部补丁作为架构主线。
