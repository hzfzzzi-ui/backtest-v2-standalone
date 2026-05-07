## ADDED Requirements

### Requirement: Universe resolver MUST 通过统一市场数据访问层消费正式市场数据
系统 MUST 让 `universe resolver` 通过统一市场数据访问层消费价格、PIT 成分、PIT 行业与证券主数据，而不是在正式主路径中继续各自直查底表。resolver SHALL NOT 再把 `pams_ohlcv_daily` 是否存在视为长期正式行情入口判断条件。

#### Scenario: 解析 HS300_ZZ500
- **WHEN** resolver 以 `HS300_ZZ500` 模式解析股票池
- **THEN** resolver MUST 通过统一市场数据访问层读取 PIT 指数成分与必要证券主数据
- **THEN** resolver SHALL NOT 在正式主路径中自行拼接 `pit_index_constituents` 直查 SQL

#### Scenario: 解析 INDUSTRY
- **WHEN** resolver 以 `INDUSTRY` 模式解析股票池
- **THEN** resolver MUST 通过统一市场数据访问层读取 PIT 行业历史与必要证券主数据
- **THEN** resolver SHALL NOT 在正式主路径中自行拼接 `pit_industry_history` 直查 SQL

### Requirement: Universe resolver MUST 保持现有 universe 语义等价
系统在把 `universe resolver` 接入统一市场数据访问层时 MUST 保持现有 `ALL_A`、`HS300_ZZ500`、`INDUSTRY` 与 `CUSTOM` 的正式 universe 语义等价。访问边界重构 SHALL NOT 单独改变 `baseline_V10.1` 的 universe 结果集合。

#### Scenario: baseline universe 回归对照
- **WHEN** 系统对 `baseline_V10.1` 执行接入前后 universe 解析回归
- **THEN** 各正式 universe 模式的结果集合 MUST 保持等价
- **THEN** 任意差异 MUST 被视为行为漂移而不是结构整理
