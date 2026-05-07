## 1. Spec 与合同收口
- [x] 1.1 完成 `fix-etf-standalone-postprocess-and-fallback-sizing` 的 proposal/design/specs 并通过 `openspec validate`。

## 2. Standalone target contract 实现
- [x] 2.1 在 `selection.py` / `execution_paths.py` 中为 standalone inter-rebalance deploy 补 `final_target_weight`，并保持 `target_weight` 继续表示 delta deploy gap。
- [x] 2.2 修正 partial fallback fill 的 postprocess/sizing，确保存在原始正目标标的时，fallback 标的的 `final_target_weight` 与 `target_weight` 都为 `0.0`，且 full fallback replacement 仍能承接 live target。

## 3. Audit 与产物对齐
- [x] 3.1 调整 `research_audit` 的 target contract drift 检测，使其优先比较 `final_target_weight`，并把 standalone delta `target_weight` 只作为 deploy gap 解释。
- [x] 3.2 保持 `orders.csv` / `audit.json` / `run_meta.json` 的最小证据字段可直接验证 drift 与 fallback sizing。

## 4. 回归与实跑
- [x] 4.1 跑 ETF provider / order planning / audit contract 回归。
- [x] 4.2 重跑 `etf/cn_broad_based_research_mainline_r1` 全窗回测，复核 `target_contract_drift_detected` 与 drift examples。

## 本轮结论
- 最新实跑：`exp_20260404_123303975_16d5`
- 结论：`target_contract_drift_detected=false`，`target_contract_drift_day_count=0`
- 说明：standalone full fallback replacement 不再因为 fallback symbol 缺 formal per-symbol target 而被误判为 drift
