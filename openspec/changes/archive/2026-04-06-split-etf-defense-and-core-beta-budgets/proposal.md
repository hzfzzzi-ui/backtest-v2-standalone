## Why

当前 ETF 腿同时承担防守、核心 beta、弱势累积与执行补丁，职责过重。需要至少先在预算和 explain 层拆开 defense 与 core beta，减少弱势问题被混成单腿 patch。

## What Changes

- 在账户层和 ETF 预算语义中拆出 `defense` 与 `core beta` 两类预算。
- 允许 ETF 仍使用单一运行引擎，但在 budget/explain/audit 上必须可分辨两种角色。
- 为后续真正切成多 sleeve 或账户配置 runtime 做准备。

## Capabilities

### New Capabilities
- `etf-defense-core-beta-budgets`: 定义 ETF 内部 defense / core beta 预算语义与 explain 边界。

## Impact

- Affected code:
  - account allocator
  - ETF explain / audit surface
  - unified runtime budget materialization
- Affected artifacts:
  - `run_meta.json`
  - ETF diagnostics
- Dependencies: 依赖账户预算已上收，但不强制拆成两个运行时 sleeve。
