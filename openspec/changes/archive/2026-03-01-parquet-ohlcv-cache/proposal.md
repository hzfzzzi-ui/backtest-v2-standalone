## Why

OHLCV 数据加载是回测全流程的绝对瓶颈（占总耗时 66-76%）。压力测试显示：5,369 只全 A 股票 × 8 年数据，`load_ohlcv_daily()` 耗时 94 秒（总耗时 141 秒）。在调参场景中，用户连续运行 10 次回测需要重复加载相同数据 940 秒。

历史行情数据在容器运行期间不会变更（新数据入库 = 容器重建），因此非常适合做进程级惰性缓存：首次加载后写入 Parquet 文件，后续回测直接从 Parquet 读取（~2-4 秒），无需重复查询 PostgreSQL。

## What Changes

- 新增 `CachedDataProvider` wrapper，实现 `DataProvider` 接口，内部包装 `PostgresDataProvider`
- 首次 `load_ohlcv_daily()` 调用触发全表 dump 到 `/tmp/ohlcv_cache.parquet`（~56 秒，含查询 + 写入）
- 后续调用从 Parquet 文件读取，使用 predicate pushdown 按日期过滤 + 内存按 symbols 过滤（~2-4 秒）
- `experiment_runner.py` 中用 `CachedDataProvider` 替换裸 `PostgresDataProvider`
- 缓存生命周期 = 容器生命周期（`/tmp` 非持久化，容器重启自动清空），无需手动失效

## Capabilities

### New Capabilities
- `parquet-ohlcv-cache`: 进程级 Parquet 缓存层，透明加速 OHLCV 数据加载

### Modified Capabilities

（无 spec 级需求变更）

## Impact

- **新增文件**: `backend/core/data/cached_provider.py`（CachedDataProvider 实现）
- **修改文件**: `backend/core/tools/experiment_runner.py`（provider 实例化处切换为 CachedDataProvider）
- **依赖**: pyarrow（已作为 pandas 的 parquet engine 存在于当前环境）
- **磁盘**: `/tmp/ohlcv_cache.parquet` 约 300-400 MB（snappy 压缩）
- **内存**: 首次 dump 时峰值与当前相当；后续读取使用 predicate pushdown 可降低峰值
- **不影响**: 回测引擎、策略、产物格式、前端 — 纯数据加载层优化
