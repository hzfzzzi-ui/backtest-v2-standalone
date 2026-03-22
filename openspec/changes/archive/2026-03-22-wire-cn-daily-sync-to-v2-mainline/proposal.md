## Why

当前 `cn_daily_sync` 的正式调度只会刷新旧链路 `pams_ohlcv_daily`，并把这张旧表的最新交易日当成“市场数据已新鲜”的判断依据。但 `baseline_V10.2` 主线实际读取的是 `pams_ohlcv_daily_v2`、`pit_stock_moneyflow_v2` 和 `CSI800 PIT`。结果是：即使旧表已经到 `2026-03-20`，只要 V2 主线仍停在 `2026-03-16`，系统也会错误地显示 fresh，并跳过后续补齐。这直接破坏了可信、可审计和可解释。

这次变更只解决一个问题：把现有 `cn_daily_sync` 接到 V2 主线，并把 freshness 判定切到 V2 主线口径，避免继续把旧表 freshness 当成正式主线 freshness。

## What Changes

- 将 `run_cn_daily_sync_once()` 从“旧表日更 + 指数桥接 + CSI800 PIT”扩展为“旧表兼容桥接 + V2 raw + V2 main + V2 moneyflow + CSI800 PIT”的正式主线日更流水线。
- 明确并固化同步顺序：`pams_ohlcv_daily` -> `pit_index_daily` -> `raw_tushare_*` -> `pams_ohlcv_daily_v2` -> `pit_stock_moneyflow_v2`/`pit_stock_moneyflow_v2_whitelist_daily` -> `csi800 PIT` -> 下游自动同步。
- 将 `market_data_sync_status` 与 run record 的 freshness 锚点切到 V2 主线，而不是 `pams_ohlcv_daily` 的 `MAX(trade_date)`。
- 在 run summary 中保留 legacy/V2 各阶段的结构化结果，方便后续审计“哪一段卡住”。

## Capabilities

### New Capabilities

### Modified Capabilities

- `cn-daily-data-sync`: 调度器必须以 V2 主线为正式补齐目标，旧表仅作为兼容桥接步骤保留。
- `market-data-freshness-status`: freshness 状态必须基于 V2 主线日期而不是旧表日期。

## Impact

- 受影响代码：
  - `backend/core/services/market_data_sync_service.py`
  - `tests/unit/test_market_data_sync_service.py`
- 受影响数据对象：
  - `pams_ohlcv_daily`
  - `pit_index_daily`
  - `raw_tushare_*`
  - `pams_ohlcv_daily_v2`
  - `pit_stock_moneyflow_v2`
  - `pit_stock_moneyflow_v2_whitelist_daily`
  - `pams_data_sync_runs`
- 不在本次变更范围：
  - 不改 baseline 策略逻辑
  - 不改 benchmark/regime 定义
  - 不改前端展示结构
