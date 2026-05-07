## ADDED Requirements

### Requirement: runtime 编译链必须支持恢复态质量过滤字段
API runtime 编译链 MUST 支持恢复态质量过滤开关与阈值字段，并保证 schema、compiler、runner 编译后的字段一致。

#### Scenario: schema 接收恢复态质量过滤字段
- **WHEN** 请求配置携带 `trans_up_recovery_quality_filter_enabled` 与阈值字段
- **THEN** schema 校验 SHALL 接收这些字段

#### Scenario: compiler 保留恢复态质量过滤字段
- **WHEN** 编译 semantic config
- **THEN** `resolved_config` MUST 保留恢复态质量过滤字段

#### Scenario: runner 下发恢复态质量过滤字段
- **WHEN** 生成 runtime `market_filter`
- **THEN** runner 编译结果 MUST 将恢复态质量过滤字段下发到运行时配置
