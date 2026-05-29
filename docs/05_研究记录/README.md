# 05 研究记录

本目录用于沉淀可审计的研究索引，重点解决 study、因子、研究窗口、代码 catalog 和结论位置分散的问题。

## 当前文件

- [因子研究登记.md](./因子研究登记.md)：当前已知因子/状态分数研究面的登记表

## 归属边界

- `docs/05_研究记录` 是研究索引，不是运行产物。
- `research/studies/**/*.study.yaml` 是 study 定义来源。
- `backend/research/*_catalog.py` 是 factor id、依赖、方向和 as-of policy 的代码来源。
- `research/study_journal` 是实际研究结论和失败模式来源。
- `outputs/` 只保存运行结果，不作为长期研究登记真相。

## 新增 study 的最小记录要求

每个新因子或状态分数 study 至少应记录：

- study_id
- asset_scope
- baseline_id 或基准锚点
- factor_ids 或 score_ids
- 对应 catalog 模块
- 三窗口或说明为什么不适用
- runner_mode
- 当前状态：`registered_research_surface`、`controlled_experiment`、`diagnostic_probe`、`demo_only`、`archived`
- 结论位置：`research/study_journal` 或明确未运行

未完成上述记录前，不得把该 study 作为正式研究面或 live 发布依据。
