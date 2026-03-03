## ADDED Requirements

### Requirement: 个股序列 API 停牌日期填充
`/api/backtest_v2/series/symbol` 端点 SHALL 返回日期连续的序列。停牌期间缺失的交易日 SHALL 用最后交易日的收盘价 forward-fill，并标记 `suspended: true`。

#### Scenario: 股票存在停牌缺口
- **WHEN** 个股在查询区间内存在停牌（数据库无行记录的交易日）
- **THEN** API 返回的 points 数组 SHALL 包含停牌日的数据点
- **THEN** 停牌日的 `open/high/low/close` SHALL 全部等于停牌前最后交易日的 `close`（归一化后）
- **THEN** 停牌日的 `nav` SHALL 等于停牌前最后交易日的 `nav`
- **THEN** 停牌日数据点 SHALL 包含 `"suspended": true`

#### Scenario: 股票无停牌
- **WHEN** 个股在查询区间内无停牌（每个交易日都有数据）
- **THEN** API 返回的 points 数组中所有数据点 SHALL 包含 `"suspended": false`
- **THEN** OHLC 值 SHALL 与原有逻辑一致（无行为变更）

#### Scenario: 停牌跨越查询区间边界
- **WHEN** 股票在查询起始日之前已停牌，查询区间内前 N 天无数据
- **THEN** 这些无数据的前 N 天 SHALL 不生成数据点（无前值可 fill）
- **THEN** 从第一个有数据的交易日开始正常输出

### Requirement: 使用交易日历确定填充范围
端点 SHALL 使用 `PostgresDataProvider.load_trading_calendar_cn()` 获取交易日历，以此确定哪些日期需要填充。

#### Scenario: 填充基于交易日历
- **WHEN** 股票在 2015-04-14 有最后交易数据，2015-12-31 恢复交易
- **THEN** 2015-04-15 到 2015-12-30 之间属于交易日历的日期 SHALL 被填充
- **THEN** 非交易日（周末、法定假日）SHALL 不出现在结果中
