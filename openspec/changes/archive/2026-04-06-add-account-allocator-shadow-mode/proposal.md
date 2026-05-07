## Why

在直接上收预算权之前，需要先把账户层逻辑做成可观测对象。否则无法确认账户层对弱势、库存和预算的解释是否符合直觉，也无法判断后续 runtime cutover 是否值得推进。

## What Changes

- 新增 `Account Allocator Shadow Mode`，只输出账户级预算建议和 explain，不接管任何真实执行。
- 为当前 runtime 增加账户层建议预算、实际预算与偏差说明。
- 保持 `A_STOCK_ETF_V1` 现有回测口径不变。

## Capabilities

### New Capabilities
- `account-allocator-shadow-mode`: 定义账户层 shadow mode 的输入、输出、解释字段和非接管约束。

## Impact

- Affected code:
  - 账户级 explain/runtime snapshot 输出路径
  - unified runtime explain surface
- Affected artifacts:
  - `run_meta.json`
  - 账户级 explain / diagnostics
- Dependencies: 依赖现有状态机、组合产物和统一 runtime，不修改其执行行为。
