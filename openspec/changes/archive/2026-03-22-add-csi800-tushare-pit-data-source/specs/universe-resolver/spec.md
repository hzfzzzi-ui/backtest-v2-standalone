## MODIFIED Requirements

### Requirement: resolver 返回元数据
resolver SHALL 返回 `(symbols, meta)` 元组，其中 `meta` 除了原有 `symbols_source`、`raw_count` 和 `universe_mode` 外，在 `PIT_DYNAMIC` 指数股票池场景下还 MUST 暴露足够的 lineage 质量字段，用于区分正式单源历史链与低保真 fallback。

#### Scenario: HS300_ZZ500 暴露正式 lineage 元数据
- **WHEN** 回测使用 `universe_mode='HS300_ZZ500'` 且 membership mode 为 `PIT_DYNAMIC`
- **THEN** `meta` 或其后续落盘的等价元信息 MUST 包含 `index_code='000906.SH'`
- **THEN** `meta` 或其后续落盘的等价元信息 MUST 包含 `membership_source`、`membership_data_quality`、`membership_history_rows` 和 `distinct_start_dates`

#### Scenario: 正式入口不得继续引用月度链为 formal lineage
- **WHEN** 系统对外暴露 `HS300_ZZ500` 的正式导入资产或 lineage 说明
- **THEN** 正式入口 MUST 指向新的 `Tushare` 历史链
- **THEN** 旧月度脚本只能作为 fallback/approximate 说明存在，MUST NOT 再被标注为 formal lineage
