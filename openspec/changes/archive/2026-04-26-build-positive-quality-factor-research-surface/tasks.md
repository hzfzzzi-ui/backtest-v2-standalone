## 1. 研究层正向质量因子目录
- [x] 1.1 新增 positive quality factor catalog，只收当前基线锚定结果下最明确偏正的质量项；DoD：catalog 元数据、中文解释、方向和 as-of 约束完整；验证：真实 study 成功输出 catalog；风险：把不稳定 context 项误收进正向质量线。

## 2. 快照与研究入口
- [x] 2.1 新增 positive quality factor snapshots 与 quality score snapshot；DoD：能按日写出 raw/normalized/rank/availability；验证：真实 study 产出 factor_snapshot/factor_score_snapshot；风险：快照字段与主线真实 provider 语义脱节。
- [x] 2.2 新增 positive quality factor study surface，并接入 `study_runner`；DoD：可通过 `.study.yaml + study_run` 跑通三窗口真实样例；验证：真实 study 成功；风险：把 quality 线和 final score 组合重新混用。

## 3. 说明与边界
- [x] 3.1 补 proposal/design/notes，明确本条 change 为 `RESEARCH_ONLY`；DoD：边界清晰，后续 runtime 接入需单独 change；验证：研究结果已生成；风险：误把研究层正向项当成已验证主线 runtime 因子。
