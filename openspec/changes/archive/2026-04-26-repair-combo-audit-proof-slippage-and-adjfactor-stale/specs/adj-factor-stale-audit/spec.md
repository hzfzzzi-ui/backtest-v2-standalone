## ADDED Requirements

### Requirement: data bundle 必须输出 adj_factor stale 统计
系统 SHALL 在 data bundle 中统计 `adj_factor` 连续缺失导致的前向填充跨度，并作为审计输入暴露。

#### Scenario: bundle 输出 stale 指标
- **WHEN** 历史行情包含 `adj_factor`
- **THEN** `adj_factor_stats` MUST 至少包含 `null_count`、`max_consecutive_missing_rows`、`max_consecutive_missing_after_valid_rows`、阈值和超阈值 symbol 计数

### Requirement: research audit 必须给出复权新鲜度判断
系统 SHALL 对 `adj_factor` stale 风险输出正式 audit gate。

#### Scenario: stale 跨度超过阈值时报警
- **WHEN** `adj_factor` 连续缺失跨度超过 warn / fail 阈值
- **THEN** `price_adjustment_integrity` MUST 输出 `WARN` / `FAIL`

#### Scenario: 组合层聚合 component 复权新鲜度
- **WHEN** 组合结果包含 stock / ETF component
- **THEN** 组合层 `price_adjustment_integrity` MUST 聚合 component 结果，而不是静默忽略 component 差异
