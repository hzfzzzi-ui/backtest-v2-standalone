## ADDED Requirements

### Requirement: 主线会计审计必须校验显式分红应收与到账闭环
主线会计审计 MUST 在 canonical accounting snapshot 中同时验证 ETF 分红应收创建、到账结转与现金/NAV 闭环。

#### Scenario: pay-date 口径下应收与到账闭环通过
- **WHEN** 某 ETF 分红在除息日创建 `dividend_receivable`，并在到账日转入 `cash`
- **THEN** 会计审计同时通过 receivable 守恒、cash 守恒与 NAV 一致性检查

#### Scenario: 分红到账缺失会被审计标记
- **WHEN** 某 ETF 分红已在除息日创建 receivable，但到账日未完成结转或重复结转
- **THEN** 会计审计 SHALL 记录对应失败样本与失败类型
