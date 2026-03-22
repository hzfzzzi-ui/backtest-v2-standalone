## ADDED Requirements

### Requirement: 股票池基础过滤区 MUST 提供科创板过滤开关
前端 workbench MUST 在股票池基础过滤区域提供科创板过滤 checkbox，并将其视为 `universe.filters.exclude_star_market` 的唯一 UI 输入源。

#### Scenario: 页面默认展示关闭状态
- **WHEN** 用户首次打开 workbench，且配置中未显式提供 `exclude_star_market`
- **THEN** 科创板过滤 checkbox SHALL 处于未勾选状态
- **THEN** 页面 SHALL 不因为默认值而改变既有草稿行为

### Requirement: Config Draft MUST 透传科创板过滤字段
`buildConfigDraft()` MUST 将科创板过滤 checkbox 的状态写入 `universe.filters.exclude_star_market`，保证前端草稿与后端配置协议一致。

#### Scenario: 勾选后构建草稿
- **WHEN** 用户勾选科创板过滤并触发运行
- **THEN** `buildConfigDraft()` SHALL 在请求配置中包含 `universe.filters.exclude_star_market=true`

### Requirement: UI 回填 MUST 恢复科创板过滤状态
`applyConfigToUI()` MUST 从已有配置读取 `universe.filters.exclude_star_market`，并回填到对应 checkbox，保证配置往返一致。

#### Scenario: 已保存配置回填
- **WHEN** 系统载入一个包含 `universe.filters.exclude_star_market=true` 的配置
- **THEN** 科创板过滤 checkbox SHALL 回填为勾选状态
