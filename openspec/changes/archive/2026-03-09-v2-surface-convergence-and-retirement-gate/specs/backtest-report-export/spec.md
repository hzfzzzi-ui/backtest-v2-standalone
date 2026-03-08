## ADDED Requirements

### Requirement: 报告导出是可选能力而非实验主协议
`report.html` 导出 MUST 被视为实验的可选导出能力，而不是实验有效性的前置条件。  
实验主结果、历史列表与标准产物读取 SHALL NOT 因为 `report.html` 缺失而失败。

#### Scenario: 实验存在 `report.html`
- **WHEN** 客户端请求导出某个存在 `report.html` 的实验报告
- **THEN** 系统 SHALL 返回该 HTML 报告内容

#### Scenario: 实验缺少 `report.html`
- **WHEN** 客户端请求导出某个不存在 `report.html` 的实验报告
- **THEN** 系统 SHALL 返回显式的“报告未生成/不可用”结果
- **THEN** 该实验的 manifest 与核心产物读取 SHALL 继续可用
