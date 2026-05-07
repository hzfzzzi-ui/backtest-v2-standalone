# account-budget-control Specification

## Purpose

定义账户层接管 stock / ETF 预算分配的正式合同，使组合预算变化先表现为账户预算变化，而不是单腿内部 patch。

## Requirements

### Requirement: 账户层必须成为 stock / ETF 预算来源

系统 SHALL 由账户层统一给出 stock / ETF 的预算分配。

#### Scenario: 生成组合预算
- **WHEN** runtime 进入组合预算阶段
- **THEN** 账户层生成 stock / ETF budgets
- **THEN** stock 与 ETF 运行路径消费该预算

### Requirement: 固定 `50/50` 只保留为 fallback baseline

系统 SHALL 将当前固定 `50/50` 视为 fallback 或静态参考，而不是唯一顶层真相。

#### Scenario: allocator 不可用时回退
- **WHEN** 账户层 allocator 被显式关闭或 budget map 缺失
- **THEN** 系统 MAY 回退到现有 `50/50`
- **THEN** 产物必须标明 fallback 来源

### Requirement: 本阶段不得提前拆 ETF 角色

系统 SHALL 在本阶段保留 ETF 作为单一运行腿。

#### Scenario: 账户层接管预算但 ETF 角色未拆
- **WHEN** 账户层开始控制 stock / ETF budgets
- **THEN** ETF 仍作为单一运行腿消费账户预算
- **THEN** defense / core beta 拆分留给后续 change
