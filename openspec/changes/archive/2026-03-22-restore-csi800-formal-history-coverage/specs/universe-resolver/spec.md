## MODIFIED Requirements

### Requirement: resolver 返回元数据
resolver SHALL 返回 `(symbols, meta)` 元组，其中 `meta` 除了原有 `symbols_source`、`raw_count` 和 `universe_mode` 外，在 `PIT_DYNAMIC` 指数股票池场景下还 MUST 暴露足够的 lineage 质量字段，用于区分正式单源历史链与低保真 fallback。

#### Scenario: HS300_ZZ500 暴露正式 lineage 元数据
- **WHEN** 回测使用 `universe_mode='HS300_ZZ500'` 且 membership mode 为 `PIT_DYNAMIC`
- **THEN** `meta` 或其后续落盘的等价元信息 MUST 包含 `index_code='000906.SH'`
- **THEN** `meta` 或其后续落盘的等价元信息 MUST 包含 `membership_source`、`membership_data_quality`、`membership_history_rows` 和 `distinct_start_dates`

#### Scenario: 正式入口改为正式历史链物化
- **WHEN** 系统对外暴露 `HS300_ZZ500` 的正式导入资产或 lineage 说明
- **THEN** 正式入口 MUST 指向“长历史 seed/正式链物化 -> replace import”
- **THEN** `Tushare trade_date` 抓取脚本只可作为正式链 tail update 来源或 fallback 说明，MUST NOT 再被描述为单独可用的全历史 formal lineage
