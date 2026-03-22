## ADDED Requirements

### Requirement: 旧桌面壳与结果工作台之间必须只通过 snapshot bridge 交换结果真相
系统 MUST 将 legacy 桌面壳与 Vue results workbench 之间的结果真相交换收口到 `runtime snapshot / ResultsWorkbenchSnapshot / bridge` 契约。legacy 壳 SHALL NOT 直接承担结果拼装与可见结果渲染职责。

#### Scenario: 加载历史实验
- **WHEN** 用户从历史列表载入一个实验
- **THEN** 桌面壳 MUST 基于 experiment manifest、surface 和 runtime snapshot 构建结果快照
- **THEN** 结果工作台 MUST 通过 bridge 消费该快照
- **THEN** 桌面壳 SHALL NOT 以 `config_id` 或旧 artifact 兜底逻辑重新解释结果真相

#### Scenario: 结果工作台已接管结果区
- **WHEN** results workbench 已经成功挂载
- **THEN** legacy 桌面壳 SHALL NOT 再直接 patch 结果区的可见 KPI、图表、漏斗或交易 DOM
- **THEN** 桌面壳 MAY 继续负责加载态、选中实验状态和桥接元数据
