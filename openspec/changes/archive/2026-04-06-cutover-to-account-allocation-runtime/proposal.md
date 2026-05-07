## Why

在 shadow mode、预算上收、状态边缘现金释放和 ETF 预算拆分都稳定后，系统应从“研究组合装配器”正式切成“账户配置中枢 runtime”。否则顶层真相仍然停留在旧的 combo 结构里。

## What Changes

- 让 `Account Allocator` 成为 runtime 唯一真相。
- 让 defense / core beta / alpha budgets 成为正式运行合同。
- 将当前 `50/50` 与现有 combo 结构降级为 baseline / benchmark / fallback reference，而不再是主 runtime 真相。

## Capabilities

### New Capabilities
- `account-allocation-runtime-cutover`: 定义账户配置中枢接管 runtime 的最终 cutover 合同。

## Impact

- Affected code:
  - unified runtime entry
  - governor / audit
  - frontend config / results explain
- Affected artifacts:
  - `input_config.json`
  - `run_config.json`
  - `run_meta.json`
  - frontend explain surfaces
- Dependencies: 依赖前四个分 change 已验证通过。
