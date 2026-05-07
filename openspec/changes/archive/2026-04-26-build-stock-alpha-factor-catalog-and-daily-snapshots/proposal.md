## Why

当前 A 股个股研究逻辑仍然大量散落在 `signal provider`、`market filter`、`ranking` 和 `runtime` 里，导致因子定义、状态判断和执行结果耦合过紧，研究结果难以复现和归因。现在需要先把个股 alpha 研究平台的第一层正式化：把“原子因子定义”和“日频因子快照”从策略逻辑里拆出来，形成可审计、可复用、可独立研究的正式产物。

## What Changes

- 新增个股 alpha 因子目录能力，统一声明第一版原子因子的元数据、数据依赖、可解释说明和标准化约定
- 新增个股 alpha 日频因子快照能力，正式输出 `raw_value / normalized_value / rank_value / availability / asof` 等研究字段
- 新增个股 alpha 因子研究入口能力，允许在不跑完整策略回放的前提下做单因子和因子组合研究
- 明确第一条 change 不改主策略行为、不改 runtime 默认消费链路、不改账户状态机

## Capabilities

### New Capabilities
- `stock-alpha-factor-catalog`: 定义个股 alpha 原子因子的正式目录、元数据合同和治理边界
- `stock-alpha-factor-snapshots`: 定义个股 alpha 因子日频快照的正式产物合同和可审计字段
- `stock-alpha-factor-study-surface`: 定义单因子/因子组合研究的正式研究入口和标准输出

### Modified Capabilities

无

## Impact

- 影响代码主路径：
  - `backend/research`
  - `backend/core`
  - `research`
  - `tests`
  - `openspec`
- 影响研究产物：
  - 个股 alpha 因子目录
  - 因子日频快照
  - 单因子与因子组合研究结果
- 本 change 不应直接影响：
  - `baseline_V10.1` 主策略行为
  - unified combo runtime 默认口径
  - ETF sleeve / account allocator / execution 路径
