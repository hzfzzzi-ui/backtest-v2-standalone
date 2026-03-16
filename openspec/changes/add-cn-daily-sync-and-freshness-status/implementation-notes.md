# Implementation Notes

## Summary

已实现 A 股日更同步与最新同步日期展示的完整链路：

- backend 新增 `market_data_sync_service`，负责：
  - 基于 `pit_trade_cal` 解析目标交易日
  - 后台调度、进程内互斥、Postgres advisory lock
  - `pams_data_sync_runs` 状态真相源建表与读写
  - `fresh/stale/running/failed/never_synced/disabled` 聚合
- `update_pams_ohlcv_daily` 抽出可复用入口，scheduler 复用正式写库链路
- 新增 `/api/backtest_v2/market_data/sync_status`
- 前端在 command bar 和状态中心显性展示最新同步日期与同步状态
- 目标交易日解析已从停更的 `pit_trade_cal` 切换到活的 Tushare `trade_cal`
- scheduler 现在只会在配置时间窗口打开后尝试自动同步，不会在白天提前把上一交易日抢跑导入
- `CN_INDEX` 远端抓取失败不再拖死整次 run；`CN_A` 股票日更可继续成功落库

## Validation

### Automated

- `pytest tests/unit/test_market_data_sync_service.py tests/unit/test_update_pams_ohlcv_daily.py tests/integration/test_market_data_sync_api.py -q`
  - 结果：`14 passed`
- `npm run build:results-workbench`
  - 结果：通过

### Compose / Runtime

- `docker compose config`
  - 结果：确认 `CN_DAILY_SYNC_ENABLED/CN_DAILY_SYNC_TIME/CN_DAILY_SYNC_TIMEZONE/CN_DAILY_SYNC_POLL_SECONDS/CN_DAILY_SYNC_RETRY_SECONDS/TUSHARE_TOKEN` 已进入 standalone 配置
- `docker compose up -d --force-recreate backtest-v2-standalone`
  - 结果：服务成功重建并启动
- `GET http://localhost:8091/api/backtest_v2/market_data/sync_status`
  - 结果：接口稳定返回状态对象，不再因数据库/交易日历异常返回 500

### Real Environment Finding

真实环境中发现库内 `pit_trade_cal` 已落后于库内现有 `CN_A` 日线：

- `target_trade_date = 2026-02-13`
- `latest_available_trade_date = 2026-03-10`

这不是前端展示问题，而是旧交易日历表本身停更。当前实现已不再依赖它作为 target trade date 真相源，改为直接读取活的 Tushare `trade_cal`。

### Manual Trigger / State Writeback

容器内手动执行：

- `run_cn_daily_sync_once(force=True)`

返回：

- `status = failed`
- `target_trade_date = 2026-02-13`
- `latest_trade_date_after = 2026-03-10`

随后查询 `pams_data_sync_runs` 最新记录，确认：

- `status = failed`
- `started_at` 已写入
- `finished_at` 已写入
- `error_text` 为 `pit_trade_cal` 落后说明

`/market_data/sync_status` 同步读到：

- `last_run_status = failed`
- `last_run_started_at/last_run_finished_at` 与状态表一致

### Manual Backfill To 2026-03-12

基于新的 live calendar 口径，我在容器内手动执行了：

- `run_cn_daily_sync_once(now=2026-03-13 17:00 Asia/Shanghai, force=True)`

结果：

- `target_trade_date = 2026-03-12`
- `status = success`
- `latest_cn_a_before = 2026-03-10`
- `latest_cn_a_after = 2026-03-12`
- `upserted_rows = 10980`

数据库验证：

- `pams_ohlcv_daily` 的 `CN_A max(trade_date)` 已更新为 `2026-03-12`
- `2026-03-11` 与 `2026-03-12` 两个交易日共写入 `10980` 行
- `pams_data_sync_runs` 中新增成功记录，`target_trade_date = 2026-03-12`

当前 `sync_status` 接口在服务重启后返回：

- `status = stale`
- `target_trade_date = 2026-03-13`
- `latest_success_trade_date = 2026-03-12`
- `latest_display_trade_date = 2026-03-12`
- `lag_days = 1`

这符合预期：系统已经补到 `2026-03-12`，但还没有自动或手工导入 `2026-03-13`。

## Residual Risks

- `pit_trade_cal` 仍是停更旧表，但它已不再阻塞新的 target trade date 解析
- `CN_INDEX` 远端源当前不稳定，本轮已改成 warning-only；如果后续需要指数同步稳定性，建议单独治理该链路
- `backend/main.py` 仍使用 FastAPI `on_event`，当前只产生 deprecation warning，不影响本次功能
- 本轮未做浏览器截图级人工验证；前端部分已通过构建和真实 API 响应驱动验证

## Rollback

如果需要回退：

1. 将 `CN_DAILY_SYNC_ENABLED=false`
2. 重建 standalone 容器
3. 如需回退 UI，再撤回前端状态展示入口和 `/market_data/sync_status` 路由
4. `pams_data_sync_runs` 可保留，不影响现有回测主链路
