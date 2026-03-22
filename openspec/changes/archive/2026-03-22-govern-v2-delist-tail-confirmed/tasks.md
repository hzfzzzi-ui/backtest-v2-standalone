## 1. 终止边界规则

- [x] 1.1 在 `update_pams_ohlcv_daily_v2.py` 中增加终止边界元数据加载与 `delist_tail_confirmed` 分类逻辑；DoD：退市尾段和代码变更退役尾段能稳定落入新状态；验证：新增/更新单测；风险：误把真实缺源洗成终止尾段。
- [x] 1.2 在 `pams_ohlcv_daily_v2_common.py` 与 SQL 合同中扩展 `row_status` 合法值；DoD：主表约束、文档与代码常量一致；验证：单测与 SQL 合同检查；风险：合同未同步导致写表失败。

## 2. 审计与 runtime

- [x] 2.1 调整 `audit_pams_ohlcv_daily_v2.py`，让 `eligible_no_source` 仅统计真 `source_unresolved`，并单列 `delist_tail_confirmed`；DoD：summary 出现独立统计且 canonical gate 口径正确；验证：audit 单测；风险：汇总口径和 exception 口径不一致。
- [x] 2.2 调整 runtime exclusion breakdown，显式排除 `delist_tail_confirmed`；DoD：runtime breakdown 不再把该状态计入 `runtime_eligible`；验证：audit/runtime 单测；风险：主表和 runtime 报表出现分歧。

## 3. 文档与回归

- [x] 3.1 更新 OpenSpec delta spec、schema/runtime contract 文档；DoD：`openspec validate --strict` 通过；验证：OpenSpec 校验；风险：spec 与实现脱节。
- [x] 3.2 重跑受影响 symbol slice 和 full-window audit，记录前后差异；DoD：产出 summary 与样本文件，能说明本次减少了多少真无源；验证：定向 rebuild + full-window audit；风险：仅局部下降但全窗口结果未复核。
