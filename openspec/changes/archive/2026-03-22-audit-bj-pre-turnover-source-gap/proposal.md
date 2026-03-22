## Why

当前 `bj_pre_20211115` 的 `turnover_rate_imputed_zero` 被统一记成 `mapping_failure`，但实查后发现主因并不是“映射没配上”，而是：

- `raw_tushare_daily` 在大量 `bj_pre` 样本上存在
- `raw_tushare_daily_basic` 在 `bj_pre` 时段大面积缺失
- AkShare fallback 对这些样本也未能稳定补出 turnover

继续把这类异常记成 `mapping_failure` 会误导后续治理优先级。

## What Changes

- 将 `bj_pre_20211115` 的 `turnover_rate_imputed_zero` cause class 从笼统的 `mapping_failure` 改成 `bj_pre_daily_basic_gap`。
- 在异常详情里补充 `basic_turnover` 诊断信息。
- 更新对应单测。
- 重刷一轮受影响 BJ 切片，确认新的 cause class 分布。

## Impact

- 受影响代码：
  - `backend/cli/managed/update_pams_ohlcv_daily_v2.py`
  - `tests/unit/test_update_pams_ohlcv_daily_v2.py`
- 受影响产物：
  - `pams_ohlcv_daily_v2_exceptions`
  - 相关 audit summary / breakdown
