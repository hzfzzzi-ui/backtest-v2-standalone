## 1. 单一 sizing 真相

- [x] 1.1 抽出共享 sizing helper，并让 `candidate_plan.py` 与 `execution_orders.py` 共用；DoD：direct target、风险预算、反波动率、等权路径不再三处各自实现；验证：相关单测；风险：轻微数值顺序变化引发基线漂移。
- [x] 1.2 把 `build_rebalance_orders()` 改成薄编排层，只复用 `candidate_plan -> execution_orders`；DoD：`portfolio_runtime.py` 不再保留第二套独立 sizing 实现；验证：`test_multi_alpha_order_planning.py`；风险：兼容入口行为与主链不一致。

## 2. 正式审计去历史别名

- [x] 2.1 删除正式审计里的 `sleeve_budget` 旧别名，只保留 `candidate_boundary / candidate_plan / execution_kernel`；DoD：正式 audit row 不再出现 `sleeve_budget`；验证：审计合同单测；风险：历史诊断脚本若仍消费旧字段会暴露问题。

## 3. 文档与回归

- [x] 3.1 同步架构文档和共享接口文档，明确 sizing 真相与正式审计边界；DoD：文档与当前实现一致；验证：人工自检；风险：文档遗漏旧口径。
- [x] 3.2 跑受影响回归并重跑 `baseline_V10.1`；DoD：关键指标、交易数、预热起点无漂移；验证：pytest + baseline 对账；风险：隐藏兼容路径仍触发分叉。
