## Why

`pre_close` 左截断锚点治理完成后，hard gate 剩余的 `turnover_rate_imputed_zero` 也已经收敛成同一批历史左截断非 traded 样本。当前 `2012-2017` 窗口只剩 `sz000156 / sz000622 / sz000805` 三个 symbol，共 `756` 行；扩到 `2007-2026`，同类 `SH/SZ` 样本共 `9853` 行。

继续把这批样本按泛化 `fallback_available` 算入有效 `critical_exception_rows`，会把“历史左截断股本/换手锚点缺口”误判成当前构建失败，和刚完成的 `pre_close` 治理口径不一致。

## What Changes

- 将符合左截断条件的 `turnover_rate_imputed_zero` 从泛化 `fallback_available` 收敛成显式 `left_censored_turnover_gap`。
- 将 `turnover_rate_imputed_zero + left_censored_turnover_gap` 纳入 `known_source_gap_rows`，不再计入 formal hard gate 的有效 `critical_exception_rows`。
- 保持 runtime 保守，不因为这次归类修正放宽默认消费。
- 重刷受影响 symbol 切片并重跑 formal audits，核对 `2012-2017` 与 `2007-2026` 的 gate 变化。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `cn-stock-v2-audit-gates`: formal gate 需要把 `turnover_rate` 左截断样本从有效 critical 中拆到 `known_source_gap_rows`。
- `cn-stock-v2-source-governance`: `turnover_rate_imputed_zero` 需要区分历史左截断锚点缺口与真实构建失败，不能继续使用泛化 `fallback_available`。

## Impact

- 受影响代码：
  - `backend/cli/managed/update_pams_ohlcv_daily_v2.py`
  - `backend/cli/managed/pams_ohlcv_daily_v2_common.py`
  - `backend/cli/managed/audit_pams_ohlcv_daily_v2.py`
- 受影响测试：
  - `tests/unit/test_update_pams_ohlcv_daily_v2.py`
  - `tests/unit/test_audit_pams_ohlcv_daily_v2.py`
- 受影响文档：
  - `docs/db/v2_source_matrix.md`
  - `docs/db/pams_ohlcv_daily_v2_runbook.md`
- 受影响产物：
  - `outputs/ops/.../formal_audits_after_policy/summary.json`
