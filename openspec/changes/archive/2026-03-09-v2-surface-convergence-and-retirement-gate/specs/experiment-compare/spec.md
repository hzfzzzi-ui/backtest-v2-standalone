## ADDED Requirements

### Requirement: 实验对比必须通过 manifest 解析标准产物
系统的实验对比能力 MUST 先读取每个实验的 `manifest.json`，再解析其中声明的 `perf` 与 `nav` 产物。  
对比流程 SHALL NOT 继续绕过 manifest 直接硬编码猜测 `perf.json` 或 `nav.csv`。

#### Scenario: 比较两个存在 manifest 的实验
- **WHEN** 客户端提交两个或以上 `exp_id` 进行对比，且这些实验都存在 manifest 与对比所需核心产物
- **THEN** 系统 SHALL 通过 manifest 中声明的相对路径读取 KPI 与 NAV 数据

#### Scenario: 某个实验缺少 `report.html`
- **WHEN** 客户端比较的实验中有某个实验缺少 `report.html`
- **THEN** 系统 SHALL 继续返回该实验的 KPI 与 NAV 对比结果

### Requirement: 实验对比必须显式处理缺失核心产物
当某个实验 manifest 缺少对比所需的核心产物声明，或其声明的核心产物读取失败时，系统 MUST 将其标记为不可比较，而不是隐式返回伪空结果。

#### Scenario: 单个实验缺少对比所需核心产物
- **WHEN** 某个 `exp_id` 的 manifest 缺少 `perf` 或 `nav` 的标准产物声明
- **THEN** 系统 SHALL 将该实验标记为不可比较并从有效对比集合中剔除

#### Scenario: 最终有效可比较实验少于两个
- **WHEN** 剔除缺失核心产物的实验后，可比较实验数量少于两个
- **THEN** 系统 SHALL 返回 404 或 400，并显式说明可比较实验数量不足
