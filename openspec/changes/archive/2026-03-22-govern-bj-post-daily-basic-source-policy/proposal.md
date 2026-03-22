## Why

当前 `BJ post-2021-11-15` 的 `turnover_rate_imputed_zero` 仍是 `2016-2026` hard gate 的最大剩余项。实库核查已经确认，这批样本的主因不是 `V2` 构建错误，而是 `raw_tushare_daily_basic` 在北交所开市后的覆盖长期不完整：

- `2021-11-15` 当天 `raw_tushare_daily` 有 `153` 行 `.BJ`，但 `raw_tushare_daily_basic` 只有 `75` 行；
- 头部样本如 `920130.BJ / 920496.BJ / 920931.BJ` 当日有 `daily`，但没有 `daily_basic`；
- 多个 symbol 直到 `2023-11 ~ 2024-04` 才第一次出现 `daily_basic`；
- `AkShare` 对这些样本在缺口期也没有稳定的 `turnover_rate` fallback。

继续把这批样本归到泛化的 `fallback_available` 并计入 hard gate，会把“已知 provider coverage gap”误当成“构建失败”。

## What Changes

- 为 `BJ post-2021-11-15` 的 `daily_basic` 覆盖断层建立正式 source policy。
- 将 `BJ post` 这批 `turnover_rate_imputed_zero` 的 cause class 从泛化的 `fallback_available` 收敛成显式的 `bj_post_daily_basic_gap`。
- 将 `bj_post_daily_basic_gap` 纳入 `known_source_gap` 聚合，不再计入 hard gate 的有效 `critical_exception_rows`。
- runtime 继续保守排除这批样本，不放开 `can_consume_v10_1`。
- 重刷 `2021-11-15 ~ 2026-03-20` 的受影响 `BJ post` 切片，并重跑 formal audits。

## Capabilities

### Modified Capabilities

- `cn-stock-v2-audit-gates`: 将 `BJ post` 的已知 provider coverage gap 与真实 critical 构建异常分离。
- `cn-stock-v2-source-governance`: `turnover_rate_imputed_zero` 对 `BJ post` 不再使用泛化 `fallback_available`。
- `cn-stock-v2-runtime-compat-governance`: runtime 继续排除 `BJ post` 的低置信 `turnover_rate`，但单独暴露这批已知源断层。

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
  - `outputs/ops/.../audit_2016_2026/summary.json`
  - `outputs/ops/.../audit_2007_2026/summary.json`
