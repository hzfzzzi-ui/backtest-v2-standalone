## 1. 固化 baseline 法源与唯一 active 规则

- [x] 1.1 为 `baseline-anchor-registration` 写入 baseline 法源规则：正式 baseline 指标只能来自 `baseline.json.linked_exp_id`；DoD：main spec 明确禁止 `index.json` / `latest_champion.json` 充当 baseline 法源；验证：`openspec/specs/baseline-anchor-registration/spec.md` 已同步 linked-exp-only 规则与冲突场景；风险：旧展示层认知仍可能与新法源冲突。
- [x] 1.2 为 `baseline-anchor-registration` 写入唯一 active 规则：同一 `effective_period` 只能有一个 active baseline；DoD：main spec 明确 `active / archived / superseded / invalid / replay_anchor` 状态与唯一性约束；验证：`baseline_access.write_baseline_record` 已加入 active 唯一性校验，`tests/unit/test_baseline_access.py` 已覆盖；风险：真正 apply 时仍需人工决定现有 baseline 的最终状态。
- [x] 1.3 为 `baseline-anchor-registration` 写入 apply 守门规则；DoD：main spec 明确任何 baseline 切换前必须向用户确认最终 baseline，并说明个股腿与 ETF/组合腿绩效；验证：main spec 已同步，且同目录已补 `apply_confirmation.md`；风险：当前 `baseline_V10_1` 的 linked experiment 不在 live outputs 中，apply 仍应阻断。

## 2. 收敛 study 为简短结论

- [x] 2.1 为 `study-conclusion-registry` 新增 study 最小留痕规范；DoD：main spec 明确 `study_id / compared_baseline_id / verdict / summary_short / exp_id / window_key / variant_name / key_metrics`；验证：已新增 `openspec/specs/study-conclusion-registry/spec.md`，并实现 `backend/research/study_conclusion_registry.py`；风险：部分 research-only study 目前没有真实 `exp_id`，会以空字符串留痕。
- [x] 2.2 修改 `study-definition-runner`，写清 study 不再沉淀为并行 baseline；DoD：main spec 明确 study 正式职责是研究判决，不是长期正式锚点；验证：`study_run` 默认 `append_to_baseline=False`，CLI 新增显式 `--append-baseline` opt-in，`tests/unit/test_study_runner.py` 已覆盖；风险：旧脚本若依赖默认 baseline append，需要显式加开关。

## 3. 固化审计层对 baseline 法源的引用

- [x] 3.1 修改 `backtest-research-audit`，要求 research audit 显式声明 baseline 真相来源；DoD：main spec 明确 compare / audit 只能引用 linked-exp 法源 baseline；验证：`experiment_compare_service.compare_experiment_to_baseline` 已输出 `baseline_source_of_truth` 与 `latest_champion` display-layer conflict 检测，`tests/unit/test_experiment_compare_service.py` 已覆盖；风险：旧展示层仍可能读取 display-layer 文件，但现在会被显式降格。

## 4. apply 前确认清单

- [x] 4.1 在 proposal/design 中明确 apply 前人工确认项；DoD：文档明确列出最终保留 baseline、其个股腿绩效、ETF/组合腿绩效、其余 baseline 降级名单；验证：`proposal.md`、`design.md` 和 `apply_confirmation.md` 已补齐；风险：当前清单已经明确指出 `baseline_V10_1` 的 linked experiment 缺失，因此本轮只完成治理收口，不执行 baseline apply。
