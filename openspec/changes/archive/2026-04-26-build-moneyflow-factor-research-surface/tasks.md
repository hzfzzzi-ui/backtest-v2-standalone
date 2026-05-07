## 1. 研究层 moneyflow 因子目录
- [x] 1.1 新增 moneyflow factor catalog，首版只收 `monthly_divergence_rate`；DoD：catalog 元数据、解释说明和 as-of 约束完整；验证：catalog unit tests；风险：因子定义与现有研究脚本口径不一致。

## 2. 快照与研究入口
- [x] 2.1 新增 moneyflow factor snapshots 与 factor score snapshot；DoD：能基于现有 moneyflow divergence 数据生成正式快照；验证：snapshot unit tests；风险：coverage gate 处理错误污染研究口径。
- [x] 2.2 新增 moneyflow factor study surface，并接入 `study_runner`；DoD：可通过 `.study.yaml + study_run` 跑通最小真实样例；验证：study runner tests + 真实样例运行；风险：形成第三套 moneyflow 研究入口。

## 3. 说明与回退
- [x] 3.1 补最小 demo/notes，明确此能力为 `RESEARCH_ONLY`；DoD：study 样例与 notes 可独立说明；验证：artifacts 完整；风险：被误读为 runtime 已接入。
