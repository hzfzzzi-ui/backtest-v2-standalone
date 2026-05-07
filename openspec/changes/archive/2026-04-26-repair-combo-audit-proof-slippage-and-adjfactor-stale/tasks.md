## 1. Combo audit proof aggregation

- [x] 1.1 为组合层新增 component run_meta 解析 helper，聚合 stock / ETF component 证据。DoD：组合 audit 能读取 `run_meta.sleeves.*` 对应结果目录；验证：阅读 helper 输出结构；风险：路径解析错指向旧产物。
- [x] 1.2 修改 `timing_alignment`，允许 `unified_combo_phase1` 通过 component-level `NEXT_OPEN` 证据转为正式 `PASS`。DoD：组合 timing gate 不再因 shell 名称停在 `UNKNOWN`；验证：新增 unit test；风险：误把 component UNKNOWN 聚合成 PASS。
- [x] 1.3 修改 `universe_lineage`，允许组合层显式继承 stock `PIT_DYNAMIC` 与 ETF `DIRECT_SYMBOLS` 证明链。DoD：组合 lineage gate 能给出 `PASS/WARN/FAIL`；验证：新增 unit test；风险：component 缺失时降级不清晰。

## 2. slippage_mode runtime semantics

- [x] 2.1 在 stage-pipeline runtime bootstrap / bridge runtime 中透传 `slippage_mode`。DoD：fill accounting 可读取显式 slippage 语义；验证：阅读 bootstrap 和 runtime 挂载字段；风险：默认值漂移。
- [x] 2.2 在 `fill_accounting.py` 实现 `price_adjustment_only` 与 `cost_only` 两种真实语义。DoD：`cost_only` 不再修改 `fill_price`；验证：新增 unit test；风险：买卖现金流方向写反。

## 3. adj_factor stale audit

- [x] 3.1 在 `data_bundle_builder.py` 统计 `adj_factor` 连续缺失 / stale 前向填充跨度。DoD：bundle `adj_factor_stats` 包含 stale 指标；验证：新增 unit test；风险：按行计数与按日计数混淆。
- [x] 3.2 在 `research_audit.py` 新增 `price_adjustment_integrity` gate，并支持组合层聚合 component 结果。DoD：组合 audit 新增正式 gate；验证：新增 unit test；风险：ETF `price_adj=none` 或无 `adj_factor` 场景误报。

## 4. 回填

- [x] 4.1 回填 notes，明确本次只修组合审计与 stage-pipeline 主路径。DoD：notes 写明范围、风险和回退；验证：文件存在；风险：后续误以为 strict runtime 已同步。
