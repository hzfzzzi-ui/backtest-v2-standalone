## ADDED Requirements

### Requirement: PAMS MUST 提供调仓包入站接口
PAMS MUST 提供正式入站接口接收 `daily_position_adjustment_package@1`。接口 MUST 完成 schema 校验、幂等校验、来源哈希校验和入库。

#### Scenario: 接收有效调仓包
- **WHEN** 研究平台提交 schema 有效且幂等键未重复的调仓包
- **THEN** PAMS MUST 保存 package header、source、clock、scope、validation 和 action 明细
- **THEN** PAMS MUST 返回接收成功状态和 `package_id`

#### Scenario: 接收无效调仓包
- **WHEN** 调仓包缺失必填字段或 schema_version 不受支持
- **THEN** PAMS MUST 拒收该调仓包
- **THEN** PAMS MUST 记录拒收原因

### Requirement: PAMS MUST 持久化 package 与 action 状态
PAMS MUST 将接收的 package 与 action 写入数据库，并为 action 提供状态字段。状态 MUST 至少覆盖 `received`、`validated`、`notified`、`needs_review`、`approved`、`rejected`、`submitted`、`partially_filled`、`filled`、`cancelled`、`expired` 和 `blocked`。

#### Scenario: package 入库后生成待通知动作
- **WHEN** PAMS 成功接收包含可展示 action 的调仓包
- **THEN** action 初始状态 MUST 可追踪
- **THEN** PAMS MUST 能按 `strategy_id`、`account_scope`、`signal_date` 查询最新 action

### Requirement: PAMS notification MUST 来源于已校验 package
PAMS app/web 或 Telegram 推送 live 调仓信息时，通知来源 MUST 是已校验并入库的调仓包。通知内容 MUST 包含来源策略、信号日期、动作摘要和风险/阻断状态。

#### Scenario: 生成 app/web 调仓通知
- **WHEN** 已校验 package 中存在待用户查看的 action
- **THEN** PAMS MUST 创建 app/web 可展示通知
- **THEN** 通知 MUST 引用 `package_id` 和相关 `action_id`

### Requirement: PAMS SHALL NOT 修改研究结论
PAMS 可以对 action 增加账户侧校验结果，但 SHALL NOT 修改研究平台给出的目标组合、策略来源、配置哈希或 reason_code。账户侧调整 MUST 另行记录为 PAMS 注解。

#### Scenario: 现金不足导致买入动作不可执行
- **WHEN** PAMS 检查到某买入 action 超过账户可用现金
- **THEN** PAMS MUST 记录账户侧 `blocked` 或 `needs_review`
- **THEN** PAMS SHALL NOT 改写调仓包中的目标持仓或研究 reason_code

### Requirement: PAMS MUST 将 action 映射到交易生命周期
当用户审批某 action 时，PAMS MUST 创建或更新交易生命周期记录，并保留 `source_package_id`、`source_action_id`、`strategy_id`、`strategy_run_id` 和 `config_hash`。

#### Scenario: 用户批准买入动作
- **WHEN** 用户在 PAMS app/web 批准某个 buy action
- **THEN** PAMS MUST 创建或更新一条交易生命周期记录
- **THEN** 该记录 MUST 保留调仓包来源痕迹
