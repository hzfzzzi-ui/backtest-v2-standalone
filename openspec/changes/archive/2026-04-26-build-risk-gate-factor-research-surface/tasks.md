## 1. 研究层 Risk Gate 因子目录
- [x] 1.1 新增 risk gate factor catalog，首版只收当前主线真实参与交易的 gate/veto/context 成分；DoD：catalog 元数据、解释说明和 as-of 约束完整；验证：真实 study 成功输出 catalog；风险：把综合排序结果误当 Risk Gate 原子因子。

## 2. 快照与研究入口
- [x] 2.1 新增 risk gate factor snapshots 与 factor score snapshot；DoD：能按日输出 gate/veto/context 的 raw/normalized/rank/availability；验证：真实 study 产出 factor_snapshot/factor_score_snapshot；风险：快照字段与主线真实语义脱节。
- [x] 2.2 新增 risk gate factor study surface，并接入 `study_runner`；DoD：可通过 `.study.yaml + study_run` 跑通最小真实样例；验证：真实样例运行；风险：把 veto/context 因子误判成 rank 因子。

## 3. 说明与边界
- [x] 3.1 补最小 demo/notes，明确此能力为 `RESEARCH_ONLY`，并登记后续拆分队列：`final_score` 与 `breakout failure / exit risk`；DoD：study 样例与 notes 可独立说明，后续队列清晰；验证：artifacts 完整；风险：三个拆分任务边界再次混用。
