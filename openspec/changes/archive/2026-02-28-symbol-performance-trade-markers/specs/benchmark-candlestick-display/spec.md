## ADDED Requirements

### Requirement: 主图必须支持个股模式与组合模式切换
前端主图 MUST 支持在“组合净值模式”和“个股对照模式”之间切换。个股模式下展示选中 symbol 曲线，并保持基准显示开关行为不变。

#### Scenario: 用户切换到个股模式
- **WHEN** 用户在结果页选择某个 symbol 并进入个股对照模式
- **THEN** 主图 SHALL 使用该 symbol 的行情序列作为主曲线
- **THEN** 基准开关开启时 SHALL 继续叠加基准曲线或 K 线

#### Scenario: 用户切换回组合模式
- **WHEN** 用户退出个股模式并返回组合模式
- **THEN** 主图 SHALL 恢复为策略组合净值与基准对照展示
- **THEN** 原有图表交互与统计文本 SHALL 保持兼容
