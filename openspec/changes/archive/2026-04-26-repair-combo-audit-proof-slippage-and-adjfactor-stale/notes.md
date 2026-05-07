## Notes

- 本次 change 只覆盖当前正式主路径：
  - 组合层 research audit
  - stage-pipeline fill accounting
  - data bundle `adj_factor` stale 审计
- 没有同步改旧 strict runtime 的 `slippage_mode` 语义。
- 组合层 `timing_alignment` / `universe_lineage` 现在走 component 证据聚合，不再依赖组合 shell 名称硬编码。
- `slippage_mode=price_adjustment_only` 保持现状；
  `slippage_mode=cost_only` 改为 `fill_price == open`，slippage 只作为现金成本进入净额。
- `adj_factor` stale 第一版阈值：
  - `warn_threshold_rows = 5`
  - `fail_threshold_rows = 20`
