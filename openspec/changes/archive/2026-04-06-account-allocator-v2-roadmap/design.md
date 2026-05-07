## Overview

本 change 是总 change，不直接修改运行时代码。它给出账户配置中枢 V2 的目标结构与迁移顺序，用于约束后续分 change 的边界。

## Target Architecture

目标结构：

- `Account Allocator`
  - 统一接收状态、风险、库存、执行约束摘要
  - 统一输出 defense / core beta / alpha 预算
  - 统一输出状态切换时的现金释放建议
- `Defense Sleeve`
- `Core Beta Sleeve`
- `Alpha Sleeve`
- `Execution Layer`

顶层原则：
- 账户层先于单腿层
- 预算先于执行
- 解释先于 patch
- sleeves 作为执行消费者，不再承担过多顶层预算职责

## Phase Breakdown

1. `add-account-allocator-shadow-mode`
   - 先让账户层可见，但不接管行为。
2. `lift-account-budget-control-to-account-layer`
   - 让账户层开始决定 stock / ETF 预算。
3. `add-state-edge-cash-release-contract`
   - 把状态切换时的现金释放上收到账户层。
4. `split-etf-defense-and-core-beta-budgets`
   - 在预算和 explain 层拆开 ETF 的防守与核心 beta 角色。
5. `cutover-to-account-allocation-runtime`
   - 最终让账户层成为 runtime 唯一真相。

## Non-Goals

- 不在本 change 内直接修改 `stock alpha`
- 不在本 change 内重新定义 regime
- 不在本 change 内直接废除当前 `A_STOCK_ETF_V1`

## Exit Criteria

- 所有分 change 均具备 proposal/design/spec/tasks
- 迁移顺序、依赖和验收口径明确
- 后续实现可以逐个推进，不再反复争论总目标架构
