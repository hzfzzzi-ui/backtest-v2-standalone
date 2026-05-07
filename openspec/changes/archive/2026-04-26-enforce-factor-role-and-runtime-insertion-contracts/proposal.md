## Why

近期个股研究反复出现“研究结论有信息量，但 runtime 接法错误”的问题，根因不是单个因子，而是系统缺少统一的“因子角色 -> 允许插入层 -> 允许动作”合同。现在如果继续靠人工记忆和局部 hook 自校验推进，研究结果仍会被错误接法污染，无法满足可审计和可复现要求。

## What Changes

- 新增统一的因子插入合同，定义 canonical 因子角色、允许插入层和允许动作的对应关系。
- 在 semantic config 校验阶段拦截非法的 asset_context 因子接法。
- 在 runtime 请求构建阶段对 runtime_config_json / workbench_config 的 asset_context 做同一套合同校验。
- 将现有 `moneyflow_overlay` 与 `holding_exit_fragility` 两条 research hook 收敛到共享合同，不再各自维护分散规则。
- 为非法接法提供稳定、可审计的错误原因，避免 silent fallback。

## Capabilities

### New Capabilities
- `factor-insertion-contracts`: 定义因子角色、插入层与动作的统一合同，并提供标准化校验结果。
- `factor-hook-contract-validation`: 在 semantic 编译与 runtime 请求构建阶段强制执行因子插入合同，覆盖现有 research hook。

### Modified Capabilities
- None.

## Impact

- 影响代码：`backend/api/backtest_v2/semantic_config_compiler.py`、`backend/core/services/experiment_runtime_service.py`、`backend/core/engine_vector/moneyflow_overlay.py`、`backend/core/engine_vector/holding_exit_fragility.py`
- 影响测试：semantic compiler、runtime request、moneyflow overlay、holding-exit fragility
- 不改 baseline 主逻辑，不改正式交易行为，只增加非法配置拦截与共享合同校验
