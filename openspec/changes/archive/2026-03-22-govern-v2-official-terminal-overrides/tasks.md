## 1. 官方 override 元数据

- [x] 1.1 在 `pams_ohlcv_daily_v2_common.py` 中增加显式官方 terminal override registry，只包含 `sh600680` 与 `sh601268`，并保留 symbol、起止日期、证据来源标签；DoD：代码中可直接读取，且默认不会命中其他 symbol；验证：单测；风险：registry 范围扩张失控。

## 2. canonical 分类与审计

- [x] 2.1 在 `update_pams_ohlcv_daily_v2.py` 中增加 override 读取与判定逻辑，仅当原始分类为 `source_unresolved` 且命中显式 override 时改记为 `delist_tail_confirmed`；DoD：`600680/601268` 可命中，`synthetic_gap_fill` 与非 registry symbol 不受影响；验证：单测；风险：把真无源 symbol 洗进 terminal 状态。
- [x] 2.2 如有必要，调整 exception 细节输出，使 override 命中的 `delist_tail_confirmed` 能暴露证据来源标签；DoD：exception 可区分普通 delist tail 与 official override；验证：单测；风险：audit 明细不可追溯。

## 3. 文档、回归与数据库验证

- [x] 3.1 更新本 change 的 delta specs 与相关运行合同文档；DoD：`openspec validate --strict` 通过；验证：OpenSpec 校验；风险：spec 与实现脱节。
- [x] 3.2 重建 `sh600680, sh601268` 的 v2 slice，并重跑 full-window audit，记录 `eligible_no_source_rows` 和残留 unresolved 变化；DoD：full-window audit 反映两只已收口且剩余 unresolved 不扩大；验证：定向 rebuild + audit summary；风险：局部重建有效但全窗口口径未复核。
