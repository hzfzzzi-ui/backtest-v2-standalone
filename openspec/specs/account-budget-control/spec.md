# account-budget-control Specification

## Purpose

定义账户层接管 stock / ETF 预算分配的正式合同，使组合预算变化先表现为账户预算变化，而不是单腿内部 patch。

## Requirements

### Requirement: 账户层必须成为 stock / ETF 预算来源

系统 SHALL 由账户层统一给出 stock / ETF 的预算分配，并同步输出 transition handoff 合同供共享执行 runtime 消费。stock 与 ETF 运行路径 MUST 把账户层 handoff 视为正式执行输入，而不是局部参考信息。

#### Scenario: 生成组合预算与状态切换预算
- **WHEN** runtime 进入组合预算与状态切换阶段
- **THEN** 账户层生成 stock / ETF budgets 以及 transition handoff 合同
- **THEN** stock 与 ETF 运行路径 MUST 消费该预算与 handoff，而不是各自发明 transition execution owner

### Requirement: 固定 `50/50` 只保留为 fallback baseline

系统 SHALL 将当前固定 `50/50` 视为 fallback 或静态参考，而不是唯一顶层真相。

#### Scenario: allocator 不可用时回退
- **WHEN** 账户层 allocator 被显式关闭或 budget map 缺失
- **THEN** 系统 MAY 回退到现有 `50/50`
- **THEN** 产物必须标明 fallback 来源
- **THEN** fallback 不得覆盖账户层正常启用时的主解释权

### Requirement: 本阶段不得提前拆 ETF 角色

系统 SHALL 在本阶段保留 ETF 作为单一运行腿，但不得继续让 ETF 局部逻辑定义账户层状态切换语义。

#### Scenario: 账户层接管预算和状态切换，ETF 角色未拆
- **WHEN** 账户层开始控制 stock / ETF budgets 与状态切换 handoff
- **THEN** ETF 仍作为单一运行腿消费账户层输出
- **THEN** defense / core beta 拆分留给后续 change
- **THEN** ETF 局部执行链只能 materialize 账户层输出，不得自行定义账户层状态切换真相
