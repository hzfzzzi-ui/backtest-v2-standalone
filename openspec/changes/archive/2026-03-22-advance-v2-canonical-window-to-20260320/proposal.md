## Why

`pams_ohlcv_daily_v2`、`pit_stock_moneyflow_v2` 和 whitelist 已经补到了 `2026-03-20`，但 `v2` 的正式窗口常量、full backfill 默认终点、audit 的 `has_full_window` 判定和 runbook 仍停在 `2026-03-16`。结果是系统会把已经补齐到 `2026-03-20` 的数据库继续判成“非 full-window”，口径失真且不可审计。

这次变更只修复 formal window 的单一真相源，并据此重跑 full-window audit。它不承诺顺带通过 canonical gate；真实 unresolved 阻塞项仍须单独暴露。

## What Changes

- 将 `v2` 正式时间窗口终点从 `2026-03-16` 统一推进到 `2026-03-20`。
- 让 `raw/main/moneyflow/audit/full_backfill` 共用同一个 official window 定义，避免 CLI 默认值、AkShare fallback 和 full-window gate 各说各话。
- 更新 `v2` runbook 与相关操作文档，确保正式示例命令不再引用过期终点。
- 重跑 `2007-01-04 ~ 2026-03-20` full-window audit，输出新的 canonical gate 结论和真实阻塞项。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `cn-stock-raw-source-governance`: `v2` 正式回填窗口和官方默认终点改为 `2026-03-20`，并要求所有正式入口共享同一终点定义。
- `cn-stock-v2-audit-gates`: full-window gate 必须基于当前 official window 判定，并在审计总结中显式输出 official window 边界，避免 stale window 误判。

## Impact

- 受影响代码：
  - `backend/cli/managed/pams_ohlcv_daily_v2_common.py`
  - `backend/cli/managed/run_pams_ohlcv_daily_v2_full_backfill.py`
  - `backend/cli/managed/audit_pams_ohlcv_daily_v2.py`
  - `tests/unit/test_run_pams_ohlcv_daily_v2_full_backfill.py`
  - `tests/unit/test_audit_pams_ohlcv_daily_v2.py`
- 受影响文档：
  - `docs/db/pams_ohlcv_daily_v2_runbook.md`
  - `docs/db/cn_daily_feature_side_tables_l2_runbook.md`
- 受影响运行产物：
  - `pams_ohlcv_daily_v2_audit_daily`
  - `outputs/ops/pams_ohlcv_daily_v2_*`
