## ADDED Requirements

### Requirement: 账户层状态分数快照产物
系统 SHALL 生成账户层日频状态分数快照，首版至少支持 `raw_value`、`normalized_value`、`availability_flag`、`asof_timestamp`、`source_trace` 和 `derived_state` 字段落盘。

#### Scenario: 单日 score 可落盘
- **WHEN** 研究模块按窗口生成账户层状态分数快照
- **THEN** 系统 SHALL 为每个日期和每个 score 输出完整快照记录

#### Scenario: 快照包含离散解释状态
- **WHEN** 连续状态分数快照被生成
- **THEN** 系统 SHALL 同步输出由这些分数映射得到的 `derived_state`

### Requirement: 离散解释状态必须由连续分数派生
系统 SHALL 将 `BULL / TRANS_UP / TRANS_DOWN / RISK_OFF` 视为连续状态分数的解释层产物，而不是主真相输入。

#### Scenario: 映射结果固定在首版四态内
- **WHEN** 系统根据账户层连续状态分数生成解释状态
- **THEN** `derived_state` SHALL 只落在 `BULL`、`TRANS_UP`、`TRANS_DOWN`、`RISK_OFF` 四个值中
