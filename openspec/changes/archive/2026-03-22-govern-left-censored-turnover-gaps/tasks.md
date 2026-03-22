## 1. Spec 与规则入口
- [x] 1.1 补充 `cn-stock-v2-audit-gates` 与 `cn-stock-v2-source-governance` delta spec，明确 `turnover_rate` 左截断样本进入 known source gap。
- [x] 1.2 在 `pams_ohlcv_daily_v2_common.py` 扩展 `KNOWN_SOURCE_GAP_ISSUE_CAUSES`，为 `turnover_rate_imputed_zero` 增加显式左截断 cause class。

## 2. Core 实现
- [x] 2.1 在 `update_pams_ohlcv_daily_v2.py` 将符合条件的非 `traded` `turnover_rate_imputed_zero` 收敛为 `left_censored_turnover_gap`。
- [x] 2.2 在 `audit_pams_ohlcv_daily_v2.py` 复用 known source gap 统计，让新的 `turnover_rate` cause class 进入 `known_source_gap_rows`。

## 3. 验证与产物
- [x] 3.1 更新 `tests/unit/test_update_pams_ohlcv_daily_v2.py` 与 `tests/unit/test_audit_pams_ohlcv_daily_v2.py`，覆盖左截断 `turnover_rate` 归类。
- [x] 3.2 更新 `docs/db/v2_source_matrix.md` 与 `docs/db/pams_ohlcv_daily_v2_runbook.md`，写清 `turnover_rate` 左截断口径。
- [x] 3.3 重刷受影响 symbol 切片并重跑 `pams_ohlcv_daily_v2_formal_audits`，核对 `2012-2017` 与 `2007-2026` summary。
- [x] 3.4 运行 `pytest` 与 `openspec validate`，确认 change 可应用。
