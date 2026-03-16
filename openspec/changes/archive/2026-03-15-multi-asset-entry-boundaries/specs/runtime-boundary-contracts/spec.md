## ADDED Requirements

### Requirement: manifest 和 runtime snapshot 必须携带薄资产上下文
系统 MUST 在 experiment manifest、runtime snapshot 和派生的结果真相中携带薄资产上下文，至少包括 `asset_scope`、`asset_profile_id`、`asset_family` 和 `market_profile_id`。

#### Scenario: 读取实验 manifest
- **WHEN** 客户端请求某个实验的 manifest
- **THEN** manifest MUST 返回该实验的薄资产上下文
- **THEN** 客户端 SHALL 能在不解析底层 config 的前提下判断实验属于哪类资产边界

#### Scenario: 读取 runtime snapshot
- **WHEN** 桌面页壳构建 runtime snapshot
- **THEN** snapshot MUST 携带与 manifest 一致的资产上下文
- **THEN** 页面 SHALL NOT 继续通过 A 股专属配置字段反推资产语义

### Requirement: surface 必须暴露资产摘要但不内联 market 细节
系统 MUST 在主 surface 中提供可被桌面端、移动端和 baseline 报告复用的薄资产摘要，但 SHALL NOT 把完整 market adapter 细节塞进 surface。

#### Scenario: 桌面端加载主 surface
- **WHEN** 桌面端读取某个实验的主 surface
- **THEN** 响应 MUST 包含薄资产摘要
- **THEN** 响应 SHALL NOT 直接内联完整 market rule 对象
