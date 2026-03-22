## ADDED Requirements

### Requirement: Runtime config compile 必须支持显式的 shadow 股票表切换
系统 MUST 允许 runtime config compile 在不改变默认行为的前提下，显式编译出指向 `pams_ohlcv_daily_v2` 的股票数据源配置。该切换 MUST 来自明确的 shadow 配置或 override，而不是由 compile 流程隐式替换默认 `stocks_table`。

#### Scenario: Shadow 配置编译为 v2 数据源
- **WHEN** 用户提供 `pams_cn_pg_v2.json` 或等价 shadow override
- **THEN** runtime config compile MUST 产出指向 `pams_ohlcv_daily_v2` 的 `stocks_table` 和相应 schema mapping
- **THEN** 其他运行时字段语义 SHALL 与默认配置保持一致

#### Scenario: 默认配置不被隐式切换
- **WHEN** 用户继续使用当前默认运行配置
- **THEN** runtime config compile SHALL 继续产出指向 `pams_ohlcv_daily` 的结果
- **THEN** compile 流程 SHALL NOT 因存在 `v2` 表而自动替换默认股票表
