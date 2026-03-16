## ADDED Requirements

### Requirement: 热点 provider façade 必须允许外部 state、precompute 和 route 模块
系统 MUST 允许热点 signal provider 通过 façade 调度外部 state owner、precompute 模块和 day route 模块，只要对外仍保持既有 `SignalProvider` 协议不变。provider façade SHALL NOT 重新退化为同时承载全部状态、预计算和 route 行为的单文件 owner。

#### Scenario: Provider façade 调度预计算
- **WHEN** 热点 provider 执行 `precompute()`
- **THEN** façade MAY 调度外部 precompute 模块完成重型矩阵与诊断准备
- **THEN** 对外 `SignalProvider.precompute()` 合同 MUST 保持不变

#### Scenario: Provider façade 调度逐日路由
- **WHEN** 热点 provider 执行 `day_signals()`
- **THEN** façade MAY 调度外部 route 模块生成当日信号
- **THEN** 对外 `DaySignals` 语义 MUST 保持不变
