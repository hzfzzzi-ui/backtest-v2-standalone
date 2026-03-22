## ADDED Requirements

### Requirement: V2 MUST 提供独立的 runtime compatibility 层
系统 MUST 在 `v2` canonical 之上提供独立的 runtime compatibility 层，用于服务 `V10.1` 等正式 baseline。runtime 层 MUST 明确表达它消费哪些 canonical 状态、字段来源与可信度范围，且 SHALL NOT 直接等同于 canonical 全量表。

#### Scenario: baseline 选择 v2 runtime
- **WHEN** 正式 baseline 配置选择 `v2` runtime 数据角色
- **THEN** 系统 MUST 读取 runtime compatibility 层
- **THEN** baseline SHALL NOT 直接读取未筛选的 canonical 全量记录

### Requirement: Runtime compatibility MUST 明确处理 unresolved 与低可信记录
系统 MUST 为 runtime compatibility 层定义 unresolved、synthetic fill、低可信 `pre_close`、低可信 `turnover_rate` 等记录的消费规则。若某类记录不满足 runtime gate，系统 MUST 将其排除或降级，而不是无差别提供给策略。

#### Scenario: unresolved 记录进入 runtime
- **WHEN** canonical 中存在 `source_unresolved` 记录
- **THEN** runtime compatibility MUST 按规则排除或显式降级该记录
- **THEN** 系统 MUST 能审计该排除或降级行为

#### Scenario: 低可信字段进入 runtime
- **WHEN** 某 canonical 行包含低可信关键字段
- **THEN** runtime compatibility MUST 按 compat 规则决定是否消费
- **THEN** 决策结果 MUST 可被门禁和报告追溯

### Requirement: Runtime compatibility MUST 支持 baseline 回归验证
系统 MUST 支持对 `v1`、canonical `v2`、runtime `v2` 进行并行回归验证，并输出行为差异、路径差异与交易签名差异。若 runtime `v2` 仍显著偏离正式 baseline，系统 MUST 阻止默认切换。

#### Scenario: 跑三路回归
- **WHEN** 系统针对正式 baseline 进行 `v1`、canonical `v2`、runtime `v2` 对照回归
- **THEN** 系统 MUST 输出三路结果的收益、风险、交易差异与关键诊断
- **THEN** 系统 MUST 给出是否允许切换默认数据源的结论
