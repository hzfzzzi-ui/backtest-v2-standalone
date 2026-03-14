## MODIFIED Requirements

### Requirement: 历史实验不再提供 HTML 报告查看入口

前端历史实验面板 SHALL 不再提供 `report.html` 查看入口，而是通过结果工作台和 Markdown 报告消费实验报告。

#### Scenario: 历史实验卡片动作
- **WHEN** 用户查看历史实验卡片
- **THEN** 卡片 MAY 提供加载实验结果与加载实验配置
- **THEN** 卡片 SHALL NOT 提供“查看 HTML 报告”动作
