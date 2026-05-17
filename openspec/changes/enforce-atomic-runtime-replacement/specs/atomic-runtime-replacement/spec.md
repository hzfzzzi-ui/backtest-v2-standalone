## ADDED Requirements

### Requirement: Runtime replacement MUST be atomic

当 runtime 启用 rotation replacement 时，系统 MUST 将一个替换 pair 视为不可拆分的卖买组合。

#### Scenario: replacement BUY is executable

- **WHEN** 一个 `ROTATION_REPLACE` 卖信号与一个 replacement 买候选在同一 runtime pass 中配对
- **AND** 该买候选满足数量、slot、现金和可交易价格约束
- **THEN** 系统 MUST 同时把对应卖单和买单写入最终订单集
- **AND** 卖单 MUST 排在对应买单之前
- **AND** 两个订单 MUST 在 metadata 中保留同一 pair 的候选、持仓和 score gap 信息

#### Scenario: replacement BUY is not executable

- **WHEN** 一个 replacement 买候选无法在同一 runtime pass 中生成有效买单
- **THEN** 系统 MUST 同时取消对应 `ROTATION_REPLACE` 卖单和买单
- **AND** 最终订单集 MUST NOT 包含孤立的 `ROTATION_REPLACE` 卖单
- **AND** debug/audit payload MUST 记录取消原因

### Requirement: Replacement execution counts MUST reflect final orders

系统 MUST 区分 replacement 的计划数量和最终执行数量。

#### Scenario: debug plan is emitted

- **WHEN** runtime 输出 `debug_plan`
- **THEN** `rotation_replace_planned_count` MUST 表示 candidate_plan 计划的 pair 数
- **AND** `rotation_replace_executed_pair_count` MUST 表示最终同时生成卖买订单的 pair 数
- **AND** `rotation_replace_cancelled_count` MUST 表示被原子合同取消的 pair 数
- **AND** `rotation_replace_count` MUST 与 `rotation_replace_executed_pair_count` 一致

### Requirement: Atomic replacement MUST preserve default baseline behavior

原子替换合同 MUST 只影响启用 replacement 的路径。

#### Scenario: replacement is disabled

- **WHEN** `rotation_replace_enabled=false`
- **THEN** 普通卖单、普通买单、候选排序、现金约束和订单集 MUST 与原有行为一致
