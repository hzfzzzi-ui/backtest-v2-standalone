## Why

当前每日定时导入只会刷新 `pams_ohlcv_daily` 和 `csi800_pit`，不会把 `CN_INDEX` 行情继续同步到 `pit_index_daily`，导致 market snapshot 与手机端持续看到过期指数告警。同时，模拟盘真实持仓快照仍停留在手工/局部触发阶段，没有接入每日自动刷新闭环，手机端无法稳定依赖最新持仓与最新 reconcile。

## What Changes

- 将 `pit_index_daily` 增量同步接入每日 A 股定时导入主链，保证 `000001.SH`、`399001.SZ`、`399006.SZ`、`000906.SH` 等指数基准在 scheduler 跑完后与 `pams_ohlcv_daily` 保持一致的新鲜度。
- 新增可配置的模拟盘持仓自动导入链路：从外部导出的 JSON 文件读取最新持仓，写入标准化 holdings snapshot，并在导入成功后自动重跑 position-aware reconcile。
- 为每日自动持仓导入增加独立运行状态、失败降级和审计输出；当外部导入文件缺失、日期落后或格式非法时，不得覆盖已有 `latest.json`。
- 将日终市场同步与模拟盘持仓自动刷新串成顺序流水线：先刷市场数据，再刷持仓快照，再生成最新 trade sheet。

## Capabilities

### New Capabilities
- `sim-account-auto-sync`: 规范模拟盘持仓快照的定时导入、标准化校验、运行状态与自动 reconcile 行为。
- `cn-index-daily-sync-bridge`: 规范每日 A 股定时导入完成后，`pit_index_daily` 必须与最新 `CN_INDEX` 行情同步。

### Modified Capabilities
- 无

## Impact

- 受影响代码：
  - `backend/core/services/market_data_sync_service.py`
  - `backend/scripts/update_pit_index_daily.py`
  - `backend/core/services/sim_account_service.py`
  - `backend/core/services/sim_account_reconcile_service.py`
  - 新增模拟盘自动导入服务与对应测试
- 受影响运行产物：
  - `outputs/ops/cn_daily_sync/...`
  - `outputs/ops/sim_account/<account_id>/holdings/latest.json`
  - `outputs/ops/sim_account/<account_id>/reconcile/latest.json`
- 受影响系统：
  - market snapshot freshness
  - mobile dashboard trade sheet
  - 每日定时导入 scheduler
