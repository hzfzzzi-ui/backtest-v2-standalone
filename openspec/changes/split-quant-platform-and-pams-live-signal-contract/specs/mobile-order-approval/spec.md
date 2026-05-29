## ADDED Requirements

### Requirement: mobile approval SHALL use PAMS transaction domain as formal boundary
移动端审批的长期正式边界 SHALL 是 PAMS 事务域。研究平台可以保留内部预览或兼容 approval ticket，但正式 app/web 审批 MUST 通过 PAMS package/action/transaction 状态完成。

#### Scenario: 用户在 app/web 审批调仓动作
- **WHEN** 用户批准或拒绝某个 live 调仓 action
- **THEN** PAMS MUST 更新对应交易生命周期记录
- **THEN** 研究平台 approval ticket SHALL NOT 成为该审批的长期主真相

### Requirement: mobile approval MUST show source and risk context
移动端审批页面 MUST 展示调仓包来源与风险上下文，至少包括 `strategy_id`、`strategy_run_id`、`signal_date`、`execution_date`、`reason_code`、`risk_flags` 和账户侧阻断状态。

#### Scenario: 查看待审批动作
- **WHEN** 用户打开某个待审批 action
- **THEN** 页面 MUST 能展示策略来源、信号日期、建议动作、原因和风险标记
- **THEN** 页面 MUST 能区分研究建议与 PAMS 账户侧校验结果
