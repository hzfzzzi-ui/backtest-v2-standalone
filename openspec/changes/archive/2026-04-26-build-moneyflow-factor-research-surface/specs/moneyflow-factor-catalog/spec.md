## ADDED Requirements

### Requirement: moneyflow factor catalog
系统 SHALL 定义独立的 moneyflow factor catalog，首版至少包含 `monthly_divergence_rate`，并为其声明中文说明、数据依赖、可用性约束、as-of 规则和解释边界。

#### Scenario: catalog declares first moneyflow factor
- **WHEN** 研究模块加载 moneyflow factor catalog
- **THEN** 系统 SHALL 返回 `monthly_divergence_rate` 的固定 `factor_id`、中文说明、依赖字段和 as-of 约束
