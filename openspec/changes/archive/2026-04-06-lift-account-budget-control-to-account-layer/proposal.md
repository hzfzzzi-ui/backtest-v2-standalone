## Why

当前顶层仍以固定 `50/50` 作为主组合形态，导致状态变化下的预算调整被压到 ETF 单腿和执行层内部。需要先把 stock vs ETF 的预算权上收到账户层，才能减少下层 patch。

## What Changes

- 让账户层正式输出并接管 stock / ETF 的预算分配。
- 保留现有 `50/50` 作为 fallback baseline 或静态参考，而不再作为唯一顶层真相。
- 保持 ETF 内部仍暂时是一条合并腿，不在本 change 里拆 defense/core beta 角色。

## Capabilities

### New Capabilities
- `account-budget-control`: 定义账户层接管 stock / ETF 预算分配的正式合同。

## Impact

- Affected code:
  - unified runtime budget compilation
  - governor / budget snapshot
- Affected artifacts:
  - `run_config.json`
  - `run_meta.json`
  - combo explain surfaces
- Dependencies: 依赖 `account-allocator-shadow-mode` 先定义预算语义和 explain 字段。
