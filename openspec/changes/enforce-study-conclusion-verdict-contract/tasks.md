## 1. 合同写入约束

- [x] 1.1 在 `study_conclusion_registry` 增加正式 verdict 归一化与校验；DoD：新记录 `verdict` 只写 `confirmed/falsified/inconclusive`，`PASS/FAIL` 进入 `gate_status`；验证：新增 registry 单测；风险：历史记录读取必须兼容。
- [x] 1.2 在 `study_runner` 写 registry 前加入 hard gate -> study verdict 映射；DoD：弱 hard gate 通过但相对 baseline 明显恶化时写 `falsified`；验证：更新 `test_study_runner.py`；风险：默认规则必须保守，不能误升 baseline。

## 2. 读取和展示约束

- [x] 2.1 更新 `study_journal` 自动摘要，按正式 verdict 统计研究结论，并单独统计 `gate_status`；DoD：`PASS` 不再被当作研究接受；验证：更新 `test_study_journal.py` 和 API 测试；风险：历史 `PASS/FAIL` 记录需要 legacy 兼容提示。
- [x] 2.2 增加 contract regression，覆盖最近 CSI1000 类场景；DoD：候选 cagr/sharpe/max_drawdown 全部恶化且 gate PASS 时，结论为 `falsified`；验证：pytest 指定测试通过；风险：测试不能依赖 outputs 运行产物。

## 3. 验证

- [x] 3.1 运行相关单元/集成测试和 OpenSpec strict validate；DoD：目标测试通过且 `openspec validate enforce-study-conclusion-verdict-contract --strict` 通过；验证：命令输出；风险：既有 dirty worktree 中无关失败需要单独说明。
