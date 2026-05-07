## 1. 研究层 final score 组成目录
- [x] 1.1 新增 final score composition catalog，首版只收当前主线真实参与 `_final_score` 合成的核心组成项；DoD：catalog 元数据、解释说明和 as-of 约束完整；验证：catalog unit tests；风险：把非组成项误并入 `_final_score` 合同。

## 2. 快照与研究入口
- [x] 2.1 新增 final score composition snapshots 与 factor score snapshot；DoD：能按日输出组成项与 `_final_score` 的 raw/normalized/rank/availability；验证：snapshot unit tests；风险：快照字段与主线真实组成脱节。
- [x] 2.2 新增 final score composition study surface，并接入 `study_runner`；DoD：可通过 `.study.yaml + study_run` 跑通最小真实样例；验证：study runner tests + 真实样例运行；风险：把组合分研究误当 runtime 排序替代。

## 3. 说明与边界
- [x] 3.1 补最小 demo/notes，明确此能力为 `RESEARCH_ONLY`，并登记后续拆分队列：`breakout failure / exit fragility`；DoD：study 样例与 notes 可独立说明，后续队列清晰；验证：artifacts 完整；风险：研究层组成合同再次和主线行为混用。
