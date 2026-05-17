## Design

### Scope

本变更是 L2 性能与可观测性改造。它只改变数据读取缓存方式和运行耗时记录，不改变策略输入内容、交易日历、调仓、撮合、绩效计算或组合调度逻辑。

### Runtime Timing

在 `run_experiment()` 使用已有 `RunContext`：

- `config_load`：读取配置、应用 overrides、创建实验目录、写 `run_config.json`。
- `data_load`：`load_config()` 与 `build_data_bundle()`。
- `simulation`：构建 strategy/runtime plan 并执行 foundation shell。
- `output_write`：投影并写出 CSV 辅助产物。
- `metrics_finalize`：重算有效观察窗口绩效、构造返回 payload、写 `run_profile.json`。

`run_profile.json` 是运行性能产物，不进入收益指标；`run_meta.run_profile` 只保存摘要，方便审计和 UI 查询。

### OHLCV Cache Namespace

缓存命名空间包含：

- PostgreSQL host/port/dbname
- `resolved_stocks_table()`
- `resolved_stocks_mapping_table()`
- cache version

文件路径放在 `OHLCV_CACHE_DIR`，默认 `/tmp/ohlcv_cache`：

- 表级缓存：`tables/{namespace}.parquet`
- 切片缓存：`slices/{namespace}/{start}_{end}_{symbol_count}_{hash}.parquet`

保留旧 `/tmp/ohlcv_cache.parquet` 清理能力，避免历史文件继续占空间。

### Slice Cache

默认 `OHLCV_CACHE_MODE=slice`：

1. 根据当前 provider 的 resolved table 判断 symbol normalization：
   - `pams_cn_etf_daily` 使用 `normalize_cn_etf_symbol()`
   - 其他股票表使用 `normalize_stock_symbol()`
2. 用 `start/end + sorted normalized symbols` 生成 slice key。
3. cache hit 时直接读 parquet。
4. cache miss 时委托 `PostgresDataProvider.load_ohlcv_daily()` 执行原有窗口 + symbol SQL，然后写入 slice parquet。
5. meta 中校验 cache version、mode、table、mapping、window、symbols hash 与 DB signature。

整表模式只作为显式回退模式保留，不作为默认路径。

### Validation

- 单测验证：
  - ETF catalog/coverage 委托不变。
  - 不同 resolved table 的 cache path 不同。
  - slice cache 对同一窗口/资产池二次命中，不再调用 inner provider。
  - ETF symbol normalization 与 Postgres provider 对齐。
- Docker 验收：
  - 清理旧 cache 后跑一次最小全量 stock+ETF 组合实验。
  - 对比优化前耗时，重点看 stock component。
  - 与正式基线或上一轮 V2 结果做指标一致性检查。
