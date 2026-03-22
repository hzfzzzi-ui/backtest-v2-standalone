## 1. Spec 与合同
- [x] 1.1 补充 `cn-stock-v2-canonical-quality-governance`、`cn-stock-v2-audit-gates`、`cn-stock-v2-source-governance` delta spec，明确 pre-window pause override 的适用边界。
- [x] 1.2 更新 `docs/db/pams_ohlcv_daily_v2_schema_contract.md`，明确 explicit override 可以基于“formal window 起点前已暂停上市 + canonical delist_date”。

## 2. Core 实现
- [x] 2.1 在 `pams_ohlcv_daily_v2_common.py` 为 `sh600286 / sz000583 / sz000699` 增加显式 override。
- [x] 2.2 在 `tests/unit/test_update_pams_ohlcv_daily_v2.py` 增加 pre-window pause override 的单测。

## 3. 数据重刷与验证
- [x] 3.1 定点重刷 `sh600286 / sz000583 / sz000699 / bj920047 / bj920090`。
- [x] 3.2 重跑 `pams_ohlcv_daily_v2_formal_audits`，验证 `2007-2026` advisory `critical_exception_rows = 0`。
- [x] 3.3 运行 `pytest` 与 `openspec validate`，确认 change 可应用。
