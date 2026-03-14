## MODIFIED Requirements

### Requirement: 报告导出必须使用 Markdown

工作台 SHALL 提供 Markdown 报告导出，不再打开或导出后端 `report.html`。

#### Scenario: 导出已有实验报告
- **WHEN** 用户点击导出报告
- **THEN** 系统 SHALL 导出当前实验的 Markdown 报告
- **THEN** 系统 SHALL NOT 打开 `report.html`

#### Scenario: 无实验结果时导出
- **WHEN** 用户点击导出报告但无已完成实验结果
- **THEN** 系统 SHALL 提示“请先运行回测”
