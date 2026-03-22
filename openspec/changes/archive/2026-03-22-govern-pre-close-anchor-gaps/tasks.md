## 1. Spec 与规则入口

- [x] 1.1 补充 `cn-stock-v2-audit-gates` 与 `cn-stock-v2-source-governance` delta spec，明确 stale exception 不计入 formal gate，`pre_close` 左截断锚点缺口记为 known source gap。
- [x] 1.2 在 `pams_ohlcv_daily_v2_common.py` 扩展 `KNOWN_SOURCE_GAP_ISSUE_CAUSES`，为 `pre_close_imputed_zero` 增加显式 cause class。

## 2. Core 实现

- [x] 2.1 在 `update_pams_ohlcv_daily_v2.py` 将符合条件的非 traded `pre_close_imputed_zero` 收敛成 `left_censored_anchor_gap`。
- [x] 2.2 在 `audit_pams_ohlcv_daily_v2.py` 改成只统计与当前主表 `build_run_id` 对齐的 symbol 级异常，并让新的 `pre_close` cause class 进入 `known_source_gap_rows`。

## 3. 验证与产物

- [x] 3.1 更新 `tests/unit/test_update_pams_ohlcv_daily_v2.py` 与 `tests/unit/test_audit_pams_ohlcv_daily_v2.py`，覆盖左截断 `pre_close` 归类和 stale exception 不计 gate。
- [x] 3.2 更新 `docs/db/v2_source_matrix.md` 与 `docs/db/pams_ohlcv_daily_v2_runbook.md`，写清 `pre_close` 左截断锚点口径与 stale exception 审计口径。
- [x] 3.3 重刷受影响 symbol 切片并重跑 `pams_ohlcv_daily_v2_formal_audits`，核对 `2016-2026` 与 `2012-2017` summary。
- [x] 3.4 运行 `pytest` 与 `openspec validate`，确认 change 可应用。
