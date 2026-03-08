## ADDED Requirements

### Requirement: API 数据访问必须走共享数据库边界
公开 API 的 benchmark/symbol 序列读取、runtime universe 验证、以及回测产物辅助 DB 查询 SHALL 通过共享数据库边界模块完成。该边界模块 MUST 统一 provider 创建、runtime 配置注入、universe resolver 调用与预过滤口径。

#### Scenario: benchmark 与 symbol 序列共享同一 runtime data access
- **WHEN** API 请求 benchmark 序列或 symbol 序列
- **THEN** 系统通过共享数据库边界模块创建 provider，并复用同一 runtime config 解析逻辑

#### Scenario: validate_data 复用同一 universe/filter 口径
- **WHEN** API 调用 `validate_data` 验证 runtime-resolved universe
- **THEN** 系统通过共享数据库边界模块完成 universe 解析、tradable filter 与辅助数据加载，且不在路由函数中直接拼接这些步骤
