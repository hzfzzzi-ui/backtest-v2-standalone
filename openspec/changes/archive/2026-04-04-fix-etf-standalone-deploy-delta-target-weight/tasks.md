## 1. OpenSpec 边界

- [x] 1.1 补齐本轮窄 L3 change 的 proposal、design、delta spec 与 tasks，使 change 进入 apply-ready 状态；DoD：`openspec validate fix-etf-standalone-deploy-delta-target-weight --type change --strict` 通过；验证：OpenSpec CLI；风险：capability 名称错误会导致归档失败。

## 2. Standalone delta target 修复

- [x] 2.1 修正 ETF standalone inter-rebalance deploy 的 `target_weight` 语义，使 emitted BUY signals 表达增量 deploy gap；DoD：已有 defense 暴露时，core BUY signal 的 `target_weight` 小于最终 symbol 目标且总和不超过 deploy gap；验证：`tests/unit/test_cn_etf_beta_signal_provider.py`；风险：若分配口径写错，可能低估 deployability。

## 3. 验证与回归

- [x] 3.1 运行针对性单元测试，确认 standalone delta target 修复未破坏 formal `TRANS_UP redeploy` 与 monthly rebalance 合同；DoD：目标测试通过；验证：`pytest`；风险：若测试只覆盖 standalone 路径，可能遗漏 formal 回归。
- [x] 3.2 重跑 ETF 单腿 `2012-2026` 回测，比较 `BULL` gap、core 暴露、`SKIP_NO_CASH` 结构与绩效变化；DoD：形成可解释对比结论；验证：回测产物；风险：修复后可能暴露 held top-up 的下一层问题。
