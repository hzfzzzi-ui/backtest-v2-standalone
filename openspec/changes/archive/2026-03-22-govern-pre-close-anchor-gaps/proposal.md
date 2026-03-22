## Why

当前 `pre_close_imputed_zero` 的有效阻塞已经收敛成两类不同问题：一类是异常表里残留的旧 `build_run_id` 记录，它们会把已经修复的行继续算进 formal audit；另一类是从 `2007-01-04` 起连续缺历史锚点的左截断样本，它们本质上是已知源边界，而不是新的构建回归。

如果继续把这两类样本都按泛化 `critical_exception_rows` 处理，会把“陈旧异常残留”和“历史左截断锚点缺口”误判成当前构建失败，影响 `v2` hard gate 的可解释性。

## What Changes

- 修正 formal audit 的异常计数口径，只统计与当前主表 `build_run_id` 对齐的 symbol 级异常，不再把过期异常残留算进 gate。
- 将符合左截断特征的 `pre_close_imputed_zero` 从泛化 `source_present_low_confidence_fill` 收敛成显式 `left_censored_anchor_gap`。
- 将 `pre_close_imputed_zero + left_censored_anchor_gap` 纳入 `known_source_gap_rows`，不再计入 formal hard gate 的有效 `critical_exception_rows`。
- runtime 继续保守排除低可信 `pre_close` 行，不因为这次归类修正放宽默认消费门槛。
- 重刷受影响的 symbol 切片并重跑 formal audits，核对 `2016-2026` 与 `2012-2017` 的 gate 变化。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `cn-stock-v2-audit-gates`: formal audit 的 `critical_exception_rows` 需要排除 stale exception，并识别 `pre_close` 左截断已知源缺口。
- `cn-stock-v2-source-governance`: `pre_close_imputed_zero` 需要区分历史左截断锚点缺口与真实构建失败，不能继续使用泛化 cause class。

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
