## 1. 运行耗时产物

- [x] 1.1 在 `run_experiment()` 中接入 `RunContext`，记录粗粒度 stage timing。
- [x] 1.2 写出 `run_profile.json`，并把摘要透传到 result / `run_meta.json`。

## 2. OHLCV 缓存隔离

- [x] 2.1 将固定 `/tmp/ohlcv_cache.parquet` 改为按 table/mapping/database 隔离的缓存命名空间。
- [x] 2.2 保留旧缓存清理能力，并让 `clear_ohlcv_cache.py` 可清理新缓存目录。
- [x] 2.3 修复 ETF 表缓存路径下 symbol normalization 固定走 A 股股票规则的问题。

## 3. Slice cache

- [x] 3.1 新增默认 `OHLCV_CACHE_MODE=slice`，按窗口和 normalized symbol set 缓存。
- [x] 3.2 保留 `OHLCV_CACHE_MODE=table` 回退路径。
- [x] 3.3 增加 cache hit/miss 审计记录。

## 4. 验证

- [x] 4.1 增加/更新缓存层单元测试。
- [x] 4.2 运行相关单测。
- [x] 4.3 在 Docker 内运行最小全量组合实验，记录耗时并做结果一致性检查。
