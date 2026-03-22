## 1. 审计语义修正

- [x] 1.1 将 `bj_pre_20211115` 的 `turnover_rate_imputed_zero` cause class 改成 `bj_pre_daily_basic_gap`；DoD：不再输出误导性的 `mapping_failure`；验证：单测；风险：根因继续被误判。
- [x] 1.2 在 `issue_detail` 中补充 `basic_turnover` 诊断信息；DoD：异常明细可直接看出是否命中过 daily_basic；验证：单测；风险：审计信息不足。

## 2. 回归与复核

- [x] 2.1 更新 `tests/unit/test_update_pams_ohlcv_daily_v2.py`；DoD：新 cause class 受测试保护；验证：pytest；风险：后续回归把旧标签带回来。
- [x] 2.2 重刷受影响 BJ 切片并复核新的 cause class 分布；DoD：summary/exception 查询能看到 `bj_pre_daily_basic_gap`；验证：实跑产物；风险：代码改了但库里仍是旧标签。
