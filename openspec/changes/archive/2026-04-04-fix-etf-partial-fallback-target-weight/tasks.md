## 1. OpenSpec 边界

- [x] 1.1 补齐本轮窄 L3 change 的 proposal、design、delta spec 与 tasks，使 change 进入 apply-ready 状态；DoD：`openspec validate fix-etf-partial-fallback-target-weight --type change --strict` 通过；验证：OpenSpec CLI；风险：capability 名称错误会导致归档失败。

## 2. Partial fallback fill 修复

- [x] 2.1 修正 ETF partial fallback fill 的 live target 压缩逻辑，只压缩原始正目标标的；DoD：partial fill 下 fallback `target_weight=0.0`，full replacement 仍可部署；验证：`tests/unit/test_cn_etf_beta_signal_provider.py`；风险：若误改 full replacement，会把 fallback 全部打空。

## 3. 验证与回归

- [x] 3.1 运行针对性单元测试，确认 partial fill 与 full replacement 两条路径合同稳定；DoD：目标测试通过；验证：`pytest`；风险：测试若只覆盖 helper 而不覆盖 provider，可能遗漏调用链问题。
- [x] 3.2 重跑 ETF 单腿 `2012-2026` 回测，比较 `SKIP_NO_CASH`、`511010` 目标金额与 `BULL/TRANS_UP` gap 变化；DoD：形成可解释对比结论；验证：回测产物；风险：该修复可能暴露更深层的现金问题，而不是直接改善收益。
