# Public Surface Convergence Retirement Gate (2026-03-08)

## 结论

截至 `v2-surface-convergence-and-retirement-gate`，公开后端表面应收敛到两条真相：

- 输入真相：`config_json`
- 消费真相：`experiment_id -> manifest.json -> declared artifacts`

这意味着 `_config_store`、`_candidate_presets`、`_experiment_history` 与旧 artifact 兼容补丁层都进入冻结兼容期。它们可以继续为迁移和历史数据服务，但不允许再承载新的产品真相。

## 冻结范围

### 1. `_config_store`

- 冻结职责：
  - 已保存配置的读写
  - 历史配置 provenance 查询
- 替代入口：
  - 公开运行：`/api/backtest_v2/experiment/run` 与 `/api/backtest_v2/experiment/run_async` 的 `config_json`
  - 公开 preview：`/api/backtest_v2/execution/preview` 的 `config_json`
- 删除前置条件：
  1. 前端运行与 preview 不再依赖 `config_id`
  2. 研究脚本不再把 `config_id` 当运行真相
  3. 基线门禁继续通过

### 2. `_candidate_presets`

- 冻结职责：
  - 锁定 baseline candidate 的兼容入口
  - candidate provenance / summary 落盘
- 替代入口：
  - 正式运行主线：前端语义 `config_json`
- 删除前置条件：
  1. 工作台 candidate 入口迁出公开 run surface，改为内部工具或独立研究入口
  2. candidate 研究不再依赖公开 API 的 preset-only 调用
  3. 基线门禁继续通过

### 3. `_experiment_history`

- 冻结职责：
  - 基于 `experiment folder + manifest` 的历史列表、删除、对比、报告导出
- 替代入口：
  - `GET /api/backtest_v2/experiments/{exp_id}/manifest`
  - `POST /api/backtest_v2/artifacts/read`
- 删除前置条件：
  1. 前端历史页面直接基于 manifest 消费
  2. compare/report 的消费逻辑彻底迁到新 surface helper
  3. 不再有 `report.html` 必需的 UI 假设

### 4. 旧 artifact 兼容补丁层

- 冻结职责：
  - 将历史结果目录补齐到稳定 manifest/artifact 协议
  - 为旧目录保留最小兼容映射
- 替代入口：
  - `manifest.json`
  - `core_artifacts`
  - `optional_artifacts`
- 删除前置条件：
  1. 所有活跃实验目录都能稳定生成 manifest
  2. 前端与脚本不再依赖硬编码 `perf.json` / `nav.csv` / `results_dir`
  3. 基线门禁继续通过，且仅允许 `report.html` 诊断漂移

## 明确禁止

- 不再向公开 run / preview 表面新增 `config_id`、`runtime_config_json`、`workbench_config`、`config_path`
- 不再把 `results_dir` 当公开消费主锚点
- 不再把 `report.html` 当历史列表、实验加载或实验对比的前置条件
- 不再向冻结层追加新的产品逻辑

## 回归门禁

后续所有 surface 收敛或淘汰动作都必须继续通过：

`python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`

锁定基线：

- `exp_20260308_021045840_cde0`

当前唯一允许的非阻塞漂移：

- `report.html` 的诊断性 hash 漂移
