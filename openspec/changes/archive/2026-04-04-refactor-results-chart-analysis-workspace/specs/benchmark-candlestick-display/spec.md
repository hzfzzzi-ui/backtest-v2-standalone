## ADDED Requirements

### Requirement: 大盘图正式默认显示 K 线与成交量
系统 SHALL 将大盘图的正式默认形态定义为 K 线 + 成交量，而不是仅展示单层价格曲线或简化兼容视图。

#### Scenario: 大盘图默认带成交量
- **WHEN** 用户查看结果工作区中的大盘图
- **THEN** 系统 MUST 默认展示 K 线和成交量
