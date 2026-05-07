## ADDED Requirements

### Requirement: 研究诊断不得反向定义正式运行真相
`backtest-research-audit` MUST 作为研究解释层存在。研究诊断 MAY 解释正式结果、拆分缺口、提供排障视图，但 SHALL NOT 反向定义正式执行合同、正式记账真相或正式组合预算真相。

#### Scenario: 研究诊断读取正式产物
- **WHEN** 研究诊断生成 audit 结论或专项诊断结论
- **THEN** 研究诊断 MUST 基于正式运行结果和正式产物做解释
- **THEN** 研究诊断 SHALL NOT 重写正式订单、正式持仓或正式预算真相

#### Scenario: 正式层与研究层同时存在字段
- **WHEN** 正式产物和研究诊断同时引用同一交易日证据
- **THEN** 正式层字段 MUST 作为正式真相来源
- **THEN** 研究层字段 MUST 被视为解释与排障字段，而不是正式执行输入
