## ADDED Requirements

### Requirement: 调仓包 MUST 使用版本化 schema
量化研究平台发布给 PAMS 的正式调仓建议 MUST 使用 `daily_position_adjustment_package@1` schema。调仓包 MUST 至少包含 header、source、clock、scope、inputs、target_positions、action_sheet、risk_flags 和 validation。

#### Scenario: 生成有效调仓包
- **WHEN** live strategy run 成功生成调仓建议
- **THEN** 调仓包 MUST 包含 `schema_version`、`package_id`、`idempotency_key`、`generated_at`、`strategy_id`、`strategy_run_id`、`baseline_id`、`config_hash`、`execution_contract_hash`、`signal_date`、`execution_date`、`account_scope` 和 `validation.status`
- **THEN** 缺失任一必填字段时调仓包 MUST 被标记为 invalid

### Requirement: action_sheet MUST 提供账户可消费动作
调仓包中的 `action_sheet` MUST 为每条动作提供账户侧可消费字段。每条动作 MUST 至少包含 `action_id`、`symbol`、`asset_class`、`market`、`action_type`、`current_qty`、`target_qty`、`delta_qty`、`suggested_qty`、`target_weight`、`reference_price`、`reference_price_basis`、`reason_code`、`reason_tags`、`blocked` 和 `expires_at`。

#### Scenario: 买入动作
- **WHEN** 某 symbol 当前未持有且目标组合要求建仓
- **THEN** action MUST 使用 `action_type=buy`
- **THEN** action MUST 记录 `suggested_qty`、`target_qty`、`target_weight`、`reference_price` 和 `reason_code`

#### Scenario: 卖出动作
- **WHEN** 某 symbol 当前持有且目标组合要求退出或减仓
- **THEN** action MUST 使用 `action_type=sell`
- **THEN** action MUST 记录 `current_qty`、`delta_qty`、`suggested_qty`、`reference_price` 和 `reason_code`

### Requirement: 调仓包 MUST 保留时间口径和执行假设
调仓包 MUST 显式记录信号时点、执行时点和参考价格口径，防止 PAMS 或前端把规划参考价误认为成交事实。

#### Scenario: PAMS 展示参考价
- **WHEN** PAMS 展示某 action 的 `reference_price`
- **THEN** 调仓包 MUST 同时提供 `reference_price_basis`
- **THEN** 客户端 MUST 能区分规划参考价和实际成交价

### Requirement: 调仓包 MUST 支持幂等接收
调仓包 MUST 提供 package 级和 action 级幂等键。PAMS 使用这些键接收时，重复提交 SHALL NOT 产生重复通知或重复交易草稿。

#### Scenario: 重复提交同一调仓包
- **WHEN** PAMS 已接收相同 `package_id` 或相同 `idempotency_key` 的调仓包
- **THEN** PAMS MUST 返回已存在状态
- **THEN** PAMS SHALL NOT 新建重复 action 或重复通知

### Requirement: blocked/no-op MUST 显式表达
当 live run 由于数据、风险、持仓、现金或门禁原因无法形成可执行动作时，调仓包 MUST 使用显式 `package_status`、`blocked` 和 `failure_reason_codes` 表达，不得静默省略。

#### Scenario: 风险门禁阻断
- **WHEN** live run 被风险门禁阻断
- **THEN** 调仓包 MUST 标记 `package_status=blocked`
- **THEN** 调仓包 MUST 记录至少一个 `failure_reason_codes`
