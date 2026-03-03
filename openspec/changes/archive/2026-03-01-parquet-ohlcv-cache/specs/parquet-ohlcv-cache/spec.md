## ADDED Requirements

### Requirement: 透明缓存 OHLCV 数据
`CachedDataProvider` 必须实现 `DataProvider` 接口，对调用方完全透明。返回的 DataFrame 必须与 `PostgresDataProvider.load_ohlcv_daily()` 的输出在 schema、列名、数据类型、排序顺序上完全一致。

#### Scenario: 首次调用触发全表 dump
- **WHEN** 容器启动后首次调用 `load_ohlcv_daily()`，且缓存文件不存在
- **THEN** 系统必须从 PostgreSQL 查询全表数据，写入 Parquet 缓存文件，然后从缓存文件中过滤并返回请求的 symbols 和日期范围

#### Scenario: 后续调用命中缓存
- **WHEN** 缓存文件已存在，再次调用 `load_ohlcv_daily()`（任意 symbols 和日期范围组合）
- **THEN** 系统必须直接从 Parquet 文件读取数据，不查询 PostgreSQL，并按 symbols 和日期范围过滤后返回

#### Scenario: 返回数据与直接查询一致
- **WHEN** 使用 `CachedDataProvider` 和 `PostgresDataProvider` 分别查询相同 symbols 和日期范围
- **THEN** 两者返回的 DataFrame 必须内容完全一致（列名、数据类型、行数、值）

### Requirement: 进程级缓存生命周期
缓存文件必须存储在容器临时目录（`/tmp`），生命周期与容器一致。不需要手动失效、TTL、版本号等机制。

#### Scenario: 容器重启后缓存自动重建
- **WHEN** Docker 容器重启后首次调用 `load_ohlcv_daily()`
- **THEN** `/tmp` 中无缓存文件，系统自动触发全表 dump 重建缓存

#### Scenario: 同容器内多次回测共享缓存
- **WHEN** 同一容器内连续运行多次回测（不同 symbols/日期范围/策略参数）
- **THEN** 所有回测共享同一个 Parquet 缓存文件，每次仅在读取时过滤

### Requirement: 其他 DataProvider 方法直接委托
`CachedDataProvider` 的 `load_benchmark_daily()`、`load_trading_calendar_cn()`、`load_st_history()` 等方法必须直接委托给内部的 `PostgresDataProvider`，不做缓存。

#### Scenario: benchmark 和 calendar 查询走 DB
- **WHEN** 调用 `load_benchmark_daily()` 或 `load_trading_calendar_cn()`
- **THEN** 请求直接转发给 `PostgresDataProvider`，返回结果不缓存

### Requirement: 原子性写入
缓存文件写入必须是原子的，避免并发回测读到写入中的不完整文件。

#### Scenario: 并发安全写入
- **WHEN** 两个回测进程同时触发首次加载
- **THEN** 系统使用临时文件 + rename 方式写入，保证读操作要么读到完整文件，要么触发自身的 dump

### Requirement: Parquet 读取使用 predicate pushdown
从缓存文件读取时，必须使用 Parquet 的 row group filtering 按日期范围过滤，减少不必要的 IO 和内存占用。

#### Scenario: 日期过滤下推到 Parquet 引擎
- **WHEN** 调用 `load_ohlcv_daily(symbols, start="2023-01-01", end="2024-12-31")` 且缓存包含 2010~2026 全量数据
- **THEN** Parquet 引擎只读取包含 2023~2024 数据的 row groups，不将 2010~2022 的数据加载到内存

### Requirement: 可观测性 — 缓存状态日志
系统必须在日志中输出缓存命中/未命中状态，供诊断使用。

#### Scenario: 日志输出缓存状态
- **WHEN** `load_ohlcv_daily()` 被调用
- **THEN** 日志输出包含：缓存是否命中、Parquet 文件大小、读取耗时、过滤后行数
