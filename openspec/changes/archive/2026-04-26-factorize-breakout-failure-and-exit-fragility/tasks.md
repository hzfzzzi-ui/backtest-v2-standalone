## 1. 研究层 breakout failure / exit fragility 因子目录
- [x] 1.1 新增 breakout failure / exit fragility factor catalog，首版只收当前主线真实参与失败/脆弱退出解释的核心成分；DoD：catalog 元数据、解释说明和 as-of 约束完整；验证：catalog unit tests；风险：把一般排序项误当失败风险因子。

## 2. 快照与研究入口
- [x] 2.1 新增 breakout failure / exit fragility snapshots 与 factor score snapshot；DoD：能按日输出 failure/fragility 的 raw/normalized/rank/availability；验证：snapshot unit tests；风险：快照字段与主线真实退出语义脱节。
- [x] 2.2 新增 breakout failure / exit fragility study surface，并接入 `study_runner`；DoD：可通过 `.study.yaml + study_run` 跑通最小真实样例；验证：study runner tests + 真实样例运行；风险：把 fragility/context 因子误判成 rank 因子。

## 3. 说明与边界
- [x] 3.1 补最小 demo/notes，明确此能力为 `RESEARCH_ONLY`；DoD：study 样例与 notes 可独立说明，失败风险边界清晰；验证：artifacts 完整；风险：研究层失败风险合同再次和 runtime exit 行为混用。
