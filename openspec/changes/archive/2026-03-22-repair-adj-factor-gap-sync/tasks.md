## 1. Updater repair 模式

- [x] 1.1 在 `backend/cli/managed/update_pams_ohlcv_daily.py` 增加 `repair_null_adj_factor` 参数与缺口日期扫描 helper，repair 模式仅在给定日期范围内重抓当前数据库存在 `adj_factor IS NULL` 的交易日。
- [x] 1.2 在 updater summary 中补充写库后 `adj_factor` 完整性审计，至少记录修复前缺口日期、修复后剩余缺口日期、剩余缺口行数与布尔 `ok`。

## 2. Sync 严格失败判定

- [x] 2.1 调整 `backend/core/services/market_data_sync_service.py`，只有在追到目标交易日且 `adj_factor` 完整性通过时才记为 `success`。

## 3. 回归验证

- [x] 3.1 补充并运行 `tests/unit/test_update_pams_ohlcv_daily.py` 与 `tests/unit/test_market_data_sync_service.py`，覆盖 repair 模式、完整性 summary、sync 失败判定三个场景。
