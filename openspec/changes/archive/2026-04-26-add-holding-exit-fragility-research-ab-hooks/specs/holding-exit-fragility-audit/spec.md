## ADDED Requirements

### Requirement: holding/exit fragility 实验必须可审计
系统 SHALL 为 holding/exit fragility 实验输出可审计的日级和持仓级诊断，至少覆盖 hook 是否启用、覆盖持仓数、命中高风险持仓数、动作建议计数，以及持仓级 entry/holding/risk 命中信息。

#### Scenario: 日级诊断记录 hook 作用面
- **WHEN** research-only holding/exit fragility hook 在某交易日运行
- **THEN** 日级产物 MUST 记录该日 hook 启用状态、可评估持仓数、命中高风险持仓数和建议动作计数

#### Scenario: 持仓级诊断记录命中对象
- **WHEN** 某持仓被 lifecycle fragility hook 命中
- **THEN** 持仓级产物 MUST 记录该持仓的 symbol、entry 日期、当前持仓天数、风险分位、命中动作和后续退出标签
