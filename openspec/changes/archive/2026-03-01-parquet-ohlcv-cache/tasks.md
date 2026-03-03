## 1. CachedDataProvider 核心实现

- [x] 1.1 创建 `backend/core/data/cached_provider.py`，实现 `CachedDataProvider` 类：包装 `PostgresDataProvider`，实现 `DataProvider` 接口；`load_ohlcv_daily()` 包含惰性全表 dump 和 Parquet 读取逻辑；其余方法直接委托给内部 provider
- [x] 1.2 实现全表 dump 逻辑：调用内部 provider 查全表（无 symbols 过滤），`to_canonical()` 后按 `(date, symbol)` 排序，使用 snappy 压缩写入 `/tmp/ohlcv_cache.parquet.tmp`，完成后 `os.replace()` 到目标路径
- [x] 1.3 实现 Parquet 读取逻辑：使用 `pd.read_parquet(filters=[("date", ">=", start), ("date", "<=", end)])` 做 predicate pushdown，然后内存过滤 symbols（`df[df["symbol"].isin(sym_set)]`）
- [x] 1.4 添加日志输出：缓存命中/未命中、文件大小、读取耗时、过滤后行数

## 2. 集成到 experiment_runner

- [x] 2.1 修改 `experiment_runner.py`：在 `run_experiment()` 中用 `CachedDataProvider(inner=provider)` 包装 `PostgresDataProvider` 实例，替换后续所有 `provider.load_ohlcv_daily()` 调用

## 3. 验证

- [x] 3.1 Docker rebuild，运行一次 SMA 回测（3 只股票基线配置），确认首次加载触发全表 dump，日志显示 cache MISS — 13,616,793 rows → 358 MB, 220s warmup
- [x] 3.2 运行第二次相同回测，确认日志显示 cache HIT，OHLCV 加载耗时 < 5 秒 — cache HIT: 0.55s, total wall 1.10s
- [x] 3.3 回归验证：对比缓存模式与无缓存模式的回测结果（daily CSV、trades CSV），确认零差异 — NaN-aware 全列比对 PASS
