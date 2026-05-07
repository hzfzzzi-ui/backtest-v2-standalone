## ADDED Requirements

### Requirement: UI 层正式只经由统一 API adapter
系统 SHALL 让桌面 UI 层正式只经由统一 API adapter 获取数据，不再允许旧全局 helper 或 UI 直连 `fetch` 充当主路径。

#### Scenario: UI 不再依赖旧全局 helper 主路径
- **WHEN** 桌面 UI 需要读取实验、配置或结果数据
- **THEN** 系统 MUST 通过统一 API adapter 访问
