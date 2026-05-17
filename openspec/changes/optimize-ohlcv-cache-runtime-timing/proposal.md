## Why

当前 `CN_STOCK_ETF_COMBO_BASELINE_V2` 全量重跑中，stock component 耗时显著高于 ETF component。已确认一部分原因来自 OHLCV 缓存层：

- 现有缓存固定写入 `/tmp/ohlcv_cache.parquet`，stock 与 ETF 会互相覆盖。
- 缓存 materialize 粒度是整张表，stock 首次加载会读取远大于本次实验窗口和资产池所需的数据。
- 主实验链路缺少稳定的 stage timing 产物，后续优化难以归因。

这次变更只解决运行性能观测与 OHLCV 缓存粒度问题，不改变选股逻辑、ETF/股票池、信号时点、成交时点、组合构建、基准或防守层口径。

## What Changes

- 在单次实验 runner 中写出 `run_profile.json`，记录 `config_load`、`data_load`、`simulation`、`output_write`、`metrics_finalize` 等阶段耗时，并把摘要透传到 `run_meta.json`。
- 将 OHLCV parquet cache 从单一全局文件改为按 `resolved_table + mapping_key + database` 隔离的表级命名空间。
- 新增默认 slice cache：按 `resolved_table + start/end + normalized symbol set` 缓存本次实验真正需要的窗口与资产池。
- 保留 `OHLCV_CACHE_MODE=table` 的整表缓存回退模式，并保留 `OHLCV_CACHE_DISABLE` / `OHLCV_CACHE_FORCE_REFRESH` 行为。

## Impact

- 影响代码：
  - `backend/core/tools/experiment_runner.py`
  - `backend/api/backtest_v2/artifacts_finalize.py`
  - `backend/core/data/cached_provider.py`
  - `tests/unit/test_cached_provider.py`
- 不影响项：
  - 不改变研究口径。
  - 不改变 runtime plan、stage pipeline 合同、信号或成交规则。
  - 不把 `outputs/` 作为源码层扩展。
- 风险：
  - slice cache key 若缺少表、窗口、symbol 或 DB signature 字段，可能错误复用缓存。
  - ETF 与 stock symbol normalization 不一致会导致缓存命中但数据为空。
  - 运行性能产物不能污染绩效指标。

## Rollback

- 设置 `OHLCV_CACHE_DISABLE=1` 可完全绕过缓存层。
- 设置 `OHLCV_CACHE_MODE=table` 可回退到整表缓存策略，但仍保留按表隔离。
- 代码回退范围集中在上述四个文件和本 OpenSpec 变更目录。
