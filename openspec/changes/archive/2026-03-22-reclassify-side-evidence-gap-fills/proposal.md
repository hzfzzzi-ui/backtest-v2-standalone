## Why

当前 `eligible_no_source` 的头部 symbol 簇，大部分并不是真正的 `missing_in_all_sources`。我直接查库后发现，这些 `source_unresolved` 行里有约 `90053/92369` 行在同日带有 `adj_factor`、`daily_basic` 或 `stk_limit` 侧证据，只是缺少 `daily` 和 `suspend_d` 主证据。继续把它们全部记成 `eligible_no_source`，会把“有侧证据的低可信补位”与“完全无源的真实缺口”混成一类，既不准确，也阻碍后续分层治理。

这次变更先聚焦 `SH/SZ` 头部簇，把“有侧证据但无成交/停牌主证据”的行从 `source_unresolved` 中剥离出来，单独记为 `synthetic_gap_fill`。真正的 `eligible_no_source` 只保留给没有任何主证据或侧证据的行。

## What Changes

- 在 `v2` canonical build 中，为 `SH/SZ` 新增“侧证据 gap fill”分类规则。
- 对同日存在 `adj_factor`、`daily_basic` 或 `stk_limit` 侧证据，但缺少 `daily` 与 `suspend_d` 的行，改记为 `synthetic_gap_fill`。
- `eligible_no_source` 只保留给真正无源的 `source_unresolved` 行；带侧证据的 gap fill 改记为独立 exception，便于审计。
- 调整逐日 audit，使 `eligible_missing_daily_count` 只反映真正无源的 unresolved，不再把侧证据 gap fill 混入其中。
- 增加回归测试，并用 symbol slice 先重建头部 unresolved 簇，再重跑 full-window audit 验证降幅。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `cn-stock-v2-canonical-quality-governance`: 明确 `SH/SZ` 中“无 `daily/suspend_d` 但有侧证据”的补位行必须记为 `synthetic_gap_fill`，不得继续归入 `source_unresolved`。
- `cn-stock-v2-audit-gates`: `eligible_no_source` 与 `eligible_missing_daily_count` 只针对真正无源的 unresolved；带侧证据的 `synthetic_gap_fill` 必须单独审计，不得混入 `eligible_no_source`。

## Impact

- 受影响代码：
  - `backend/cli/managed/update_pams_ohlcv_daily_v2.py`
  - `backend/cli/managed/audit_pams_ohlcv_daily_v2.py`
  - `tests/unit/test_update_pams_ohlcv_daily_v2.py`
  - `tests/unit/test_audit_pams_ohlcv_daily_v2.py`
- 受影响数据：
  - `pams_ohlcv_daily_v2`
  - `pams_ohlcv_daily_v2_exceptions`
  - `pams_ohlcv_daily_v2_audit_daily`
