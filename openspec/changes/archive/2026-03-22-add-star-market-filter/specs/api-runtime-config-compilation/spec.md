## ADDED Requirements

### Requirement: 语义配置校验 MUST 接受科创板过滤字段
后端语义配置 schema MUST 接受 `universe.filters.exclude_star_market` 布尔字段，并将其视为合法的 universe filter 配置项。

#### Scenario: 请求携带布尔开关
- **WHEN** 客户端提交 `universe.filters.exclude_star_market=true`
- **THEN** 语义配置校验 SHALL 通过
- **THEN** 该字段 SHALL 保留在规范化后的配置对象中

### Requirement: Runtime compile MUST 透传科创板过滤字段
运行时配置编译 MUST 将 `universe.filters.exclude_star_market` 原样透传到 canonical runtime config，确保真实回测执行口径与前端草稿一致。

#### Scenario: 编译开启科创板过滤的草稿
- **WHEN** workbench 草稿包含 `universe.filters.exclude_star_market=true`
- **THEN** runtime config SHALL 包含 `universe.filters.exclude_star_market=true`

#### Scenario: 缺省字段保持旧行为
- **WHEN** workbench 草稿未提供 `exclude_star_market`
- **THEN** runtime compile SHALL 不引入改变既有默认口径的隐式真值
- **THEN** 旧配置在编译后 SHALL 继续保持与改动前等价的 runtime 语义
