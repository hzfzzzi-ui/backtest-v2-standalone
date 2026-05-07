## Why

`docs/04_重构思路` 已经明确当前系统的主要结构问题不再是单条腿收益不足，而是账户层真相过弱、ETF 腿职责过重、状态切换时的现金释放与预算控制没有被上收。继续在单腿内部堆 patch 会让系统越来越像研究拼装器，而不是个人多资产配置中枢。

## What Changes

- 建立 `Account Allocator V2` 的总 change，定义最终目标架构与迁移顺序。
- 将迁移拆成五个分 change：shadow mode、预算上收、状态边缘现金释放、ETF defense/core beta 预算拆分、最终 runtime cutover。
- 明确总 change 只定义总目标、阶段依赖和验收顺序，不直接承载实现细节。

## Capabilities

### New Capabilities
- `account-allocation-architecture`: 定义账户配置中枢 V2 的正式目标架构、角色分层与迁移边界。

## Impact

- Affected specs:
  - `docs/04_重构思路/*`
  - 后续五个分 change 的 proposal/design/spec/tasks
- Affected runtime: 本 change 本身不直接修改运行时。
- Dependencies: 依赖当前 `A_STOCK_ETF_V1` 主线与现有 unified runtime 合同作为迁移基座。
