## ADDED Requirements

### Requirement: `manifest.json` 是公开产物发现的唯一标准入口
系统 MUST 将 `manifest.json` 作为公开实验产物发现的唯一标准入口。  
公开消费侧 SHALL 先读取 manifest，再依据 manifest 中声明的相对路径解析标准产物与可选导出物。

#### Scenario: 实验稳定化完成后生成 manifest
- **WHEN** 一次实验完成稳定化写盘
- **THEN** `manifest.json` SHALL 声明核心产物、配置快照和可选导出物的相对路径

#### Scenario: 公开消费侧读取实验产物
- **WHEN** 前端或脚本需要读取某个实验的 `perf`、`nav`、`trades`、`run_meta` 或配置快照
- **THEN** 系统 SHALL 允许其通过 manifest 中声明的相对路径读取，而不是要求硬编码文件名猜测

### Requirement: 可选导出物必须在 manifest 中显式标记可用性
`report.html` 等导出型产物 MUST 在 manifest 中以可选导出物方式显式声明，并附带可用性状态。  
缺失可选导出物 SHALL NOT 使实验主结果无效。

#### Scenario: `report.html` 已生成
- **WHEN** 某实验目录存在 `report.html`
- **THEN** manifest SHALL 将其标记为可选导出物且状态为可用

#### Scenario: `report.html` 未生成
- **WHEN** 某实验目录不存在 `report.html`
- **THEN** manifest SHALL 将其标记为可选导出物且状态为缺失或未生成
- **THEN** 该实验的核心产物发现与主结果读取 SHALL 继续可用
