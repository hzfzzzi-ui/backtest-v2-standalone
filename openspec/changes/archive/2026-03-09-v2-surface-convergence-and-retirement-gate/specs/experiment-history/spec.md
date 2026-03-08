## ADDED Requirements

### Requirement: 历史列表与实验加载不得依赖 `report.html`
系统的实验历史列表、实验加载和实验清理能力 MUST 围绕实验目录、`manifest.json` 与标准核心产物工作。  
`report.html` 缺失 SHALL NOT 使实验从历史列表中消失，也 SHALL NOT 阻止实验被重新加载。

#### Scenario: 实验存在 manifest 与核心产物但没有 `report.html`
- **WHEN** 客户端请求实验历史列表
- **THEN** 系统 SHALL 继续返回该实验记录，而不是因为缺少 `report.html` 将其过滤

#### Scenario: 加载无报告实验
- **WHEN** 客户端请求加载一个缺少 `report.html` 但存在 manifest 与核心产物的实验
- **THEN** 系统 SHALL 继续返回该实验的标准产物信息与加载结果

### Requirement: 历史索引必须区分核心产物可用性与报告可用性
实验历史索引与相关 API MUST 分别表达“核心产物可用”与“报告可用”两类状态，避免把导出物状态误当成实验有效性。

#### Scenario: 核心产物存在但报告缺失
- **WHEN** 系统扫描某个实验目录
- **THEN** 历史记录 SHALL 体现该实验核心产物可用
- **THEN** 历史记录 SHALL 单独体现报告不可用或未生成

#### Scenario: 实验目录或 manifest 缺失
- **WHEN** 历史索引中的某条记录对应目录不存在，或目录已缺失 manifest 与核心产物
- **THEN** 系统 SHALL 在历史列表返回时将其视为孤儿记录并清理
