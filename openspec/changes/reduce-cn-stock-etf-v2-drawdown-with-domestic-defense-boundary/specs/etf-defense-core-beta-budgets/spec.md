## ADDED Requirements

### Requirement: 本轮研究必须输出 defense 与 core beta 暴露拆分

系统 SHALL 在本轮研究产物中输出 ETF sleeve 的 defense 与 core beta 目标、实际和偏差。

#### Scenario: 生成弱状态暴露报告
- **WHEN** 本轮研究运行完成
- **THEN** 报告 MUST 包含 `defense_target_exposure`、`defense_actual_exposure`
- **THEN** 报告 MUST 包含 `core_beta_target_exposure`、`core_beta_actual_exposure`
- **THEN** 报告 MUST 给出弱状态下偏离目标的原因码

### Requirement: 行业主题 ETF 不得承担防守仓语义

系统 SHALL 将行业/主题 ETF 与 defense budget 分离，避免主题动量污染防守层解释。

#### Scenario: 行业主题 ETF 在研究池中存在
- **WHEN** ETF 被分类为 `satellite_industry_theme`
- **THEN** 它 MAY 参与进攻段卫星研究
- **THEN** 它 SHALL NOT 被计入 defense exposure
