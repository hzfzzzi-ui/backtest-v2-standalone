## Why

`SH/SZ` side-evidence 尾巴已经清到只剩真无源行。最新全窗口 audit 显示，剩余 `eligible_no_source` 的主体已经切换为 `bj_post_20211115`，且这批行几乎全部在同日保留了 `adj_factor`、`daily_basic` 或 `stk_limit` 侧证据。继续把它们混记为 `eligible_no_source`，会把“有侧证据的低可信补位”与“完全无源缺口”继续混成一类，阻碍后续按问题类型治理。

这次变更只把 `BJ post-2021-11-15` 纳入与 `SH/SZ` 相同的 side-evidence gap fill 归类规则，明确不触碰 `bj_pre_20211115` 的 mapping 治理边界，也不放宽 runtime 消费口径。

## What Changes

- 扩展 `v2` canonical build 的 side-evidence gap fill 规则到 `bj_post_20211115`。
- 对缺少 `daily` 与 `suspend_d`，但同日存在 `adj_factor`、`daily_basic` 或 `stk_limit` 任一侧证据的 `BJ post-2021-11-15` 行，改记为 `synthetic_gap_fill`。
- `eligible_no_source` 继续只保留给真正无源的 `source_unresolved` 行；带侧证据的 `BJ post-2021-11-15` gap fill 记为独立 exception。
- 维持 `bj_pre_20211115` 的现有治理口径不变。
- 维持 runtime 对 `synthetic_gap_fill` 的排除语义不变。

## Capabilities

### Modified Capabilities

- `cn-stock-v2-canonical-quality-governance`: 明确 `BJ post-2021-11-15` 中带同日侧证据、但缺 `daily/suspend_d` 的补位行也必须记为 `synthetic_gap_fill`；`bj_pre_20211115` 仍不在本规则内。
- `cn-stock-v2-audit-gates`: `eligible_no_source` 与 `eligible_missing_daily_count` 继续只统计真无源 unresolved；`BJ post-2021-11-15` 的 side-evidence gap fill 必须单独审计，不得混入 `eligible_no_source`。

## Impact

- 受影响代码：
  - `backend/cli/managed/update_pams_ohlcv_daily_v2.py`
  - `tests/unit/test_update_pams_ohlcv_daily_v2.py`
- 受影响数据：
  - `pams_ohlcv_daily_v2`
  - `pams_ohlcv_daily_v2_exceptions`
  - `pams_ohlcv_daily_v2_audit_daily`
