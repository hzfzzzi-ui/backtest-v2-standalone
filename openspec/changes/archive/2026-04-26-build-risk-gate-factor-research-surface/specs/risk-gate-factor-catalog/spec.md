## ADDED Requirements

### Requirement: risk gate factor catalog
系统 SHALL 定义独立的 risk gate factor catalog，首版至少覆盖当前主线真实交易中明确参与 gate/veto/soft-weight 的 risk gate 成分，并为其声明中文说明、数据依赖、可用性约束、as-of 规则和解释边界。

#### Scenario: catalog declares first-wave risk gate factors
- **WHEN** 研究模块加载 risk gate factor catalog
- **THEN** 系统 SHALL 返回首版 risk gate 因子的固定 `factor_id`、中文说明、依赖字段和 as-of 约束
- **THEN** catalog MUST 区分 gate/veto/context 因子与综合 `final_score` 结果
