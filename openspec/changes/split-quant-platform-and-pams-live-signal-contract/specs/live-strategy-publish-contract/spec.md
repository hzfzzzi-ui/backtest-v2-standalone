## ADDED Requirements

### Requirement: live strategy MUST 先注册再发布
量化研究平台 MUST 提供 live strategy registry。任何策略在发布正式调仓包前，MUST 在 registry 中记录身份、状态、基线、配置、执行合同、适用账户范围和人工批准痕迹。

#### Scenario: 注册 live 策略
- **WHEN** 某策略准备进入实盘推送流程
- **THEN** registry MUST 记录 `strategy_id`、`status`、`baseline_id`、`config_path`、`config_hash`、`execution_contract_hash`、`asset_scope`、`account_scopes`、`publish_schedule` 和 `approval_record`
- **THEN** 缺失任一必填字段时系统 SHALL NOT 发布正式调仓包

### Requirement: only live_approved strategy SHALL publish package
只有 `status=live_approved` 的策略 SHALL 生成并推送正式 `daily_position_adjustment_package@1`。`research_only`、`shadow`、`ab_test`、`retired` 或等价状态的策略 MUST NOT 进入 PAMS 主通知流。

#### Scenario: shadow 实验产生日度结果
- **WHEN** shadow 或 AB 实验生成了 action sheet
- **THEN** 系统 MUST 将结果标记为 research-only
- **THEN** 系统 SHALL NOT 向 PAMS 发布正式调仓包

### Requirement: 每日 live run MUST 输出成功包或显式失败状态
每个启用的 live strategy 在其发布窗口内 MUST 产生一个调仓包、一个 no-op 包或一个显式失败状态。系统 SHALL NOT 静默跳过。

#### Scenario: 无需调仓
- **WHEN** live run 完成且目标持仓与当前持仓无有效差异
- **THEN** 系统 MUST 生成 `package_status=no_op` 的调仓包
- **THEN** 调仓包 MUST 记录 `strategy_run_id`、`signal_date`、`execution_date` 和 no-op 原因

#### Scenario: 数据不满足发布条件
- **WHEN** 市场数据、持仓快照、现金快照或风险门禁不满足发布要求
- **THEN** 系统 MUST 生成显式失败状态或 blocked 包
- **THEN** 失败状态 MUST 包含 `failure_reason_codes`

### Requirement: 发布前 MUST 校验研究来源哈希
正式发布前，系统 MUST 校验 `config_hash`、`execution_contract_hash` 和 `baseline_id` 与 registry 中记录一致。校验失败时 SHALL NOT 发布正式调仓包。

#### Scenario: 配置哈希发生漂移
- **WHEN** live run 生成的 `config_hash` 与 registry 记录不一致
- **THEN** 系统 MUST 阻断发布
- **THEN** 阻断结果 MUST 记录 `config_hash_mismatch`
