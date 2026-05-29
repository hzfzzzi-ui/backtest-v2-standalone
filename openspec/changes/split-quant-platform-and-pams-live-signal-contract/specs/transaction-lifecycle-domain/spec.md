## ADDED Requirements

### Requirement: transaction lifecycle MUST preserve package lineage
交易生命周期主表 MUST 保留来自调仓包的来源痕迹。每条由 live 调仓包产生的交易生命周期记录 MUST 至少包含 `source_package_id`、`source_action_id`、`strategy_id`、`strategy_run_id`、`signal_date` 和 `config_hash`。

#### Scenario: action 进入审批
- **WHEN** PAMS 将某调仓包 action 转为待审批交易记录
- **THEN** 交易生命周期记录 MUST 保留 package 和 action 来源字段
- **THEN** 审计方 MUST 能从交易记录追溯到原始调仓包

### Requirement: PAMS transaction lifecycle SHALL be long-term truth
PAMS 事务域 SHALL 成为审批、提交、部分成交、成交、拒绝、撤销、过期等状态的长期真值。研究平台文件型 approval ticket 和 execution event SHALL 仅作为过渡兼容或审计镜像。

#### Scenario: 查询某动作执行状态
- **WHEN** app/web 查询某 live 调仓动作的执行状态
- **THEN** 系统 MUST 从 PAMS 交易生命周期读取状态
- **THEN** 系统 SHALL NOT 依赖研究平台 `outputs/mobile_ops/*` 文件作为长期真值
