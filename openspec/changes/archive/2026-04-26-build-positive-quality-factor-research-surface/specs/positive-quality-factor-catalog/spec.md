## ADDED Requirements

### Requirement: positive quality factor catalog
系统 SHALL 定义独立的正向质量因子目录，首版只覆盖当前基线锚定研究中最明确偏正的质量项，并为其声明中文说明、方向、as-of 规则和解释边界。

#### Scenario: catalog declares first-wave positive quality factors
- **WHEN** 研究模块加载 positive quality factor catalog
- **THEN** 系统 SHALL 返回首版正向质量因子的固定 `factor_id`、中文说明、方向和 as-of 约束
- **THEN** 首版 catalog MUST 只包含 `volume_price_quality_score` 与 `breakout_quality_score`
