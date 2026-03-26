# Implementation Notes

## Summary

`build-cn-stock-etf-unified-runtime-entry` 已实现到可归档状态。当前 `cfg_cn_stock_etf_v1` 不再只是 research combo 锚点，而是能触发一次真正的 unified runtime：

- 单次实验同时运行 `cn_stock_trend_alpha_core`
- 单次实验同时运行 `cn_etf_beta`
- 输出组合级 `run_meta / audit / manifest / portfolio_daily / nav`
- 输出股票 sleeve 与 ETF sleeve 的组件摘要

本轮没有把 ETF 升格为正式收益主线，也没有引入新的 sleeve。

## Key Changes

- 新增 unified runtime orchestrator：
  - `backend/core/services/cn_stock_etf_unified_runtime_service.py`
- research audit 新增 unified runtime 完整性 gate，并修正 unified combo attribution traceability 判定：
  - `backend/core/audit/research_audit.py`
- 前端结果工作台区分：
  - `unified_runtime_combo`
  - `research_combo`
  不再把 unified combo 误判成 research combo：
  - `frontend/app/results-workbench/helpers/resultsFormatting.js`
  - `frontend/app/results-workbench/App.vue`
  - `frontend/app/results-workbench/components/ResearchComboPanel.vue`
  - `frontend/app/results-workbench/components/ResearchComboChart.vue`
- `cfg_cn_stock_etf_v1` 升级为 unified runtime 入口模板：
  - `outputs/configs/cfg_cn_stock_etf_v1.json`

## Verification

### Unit / Frontend

- `pytest tests/unit/test_research_audit_contract.py tests/unit/test_cn_stock_etf_unified_runtime_service.py tests/unit/test_experiment_query_service.py -q`
- `node --test tests/frontend/test_results_workbench_multi_alpha.mjs tests/frontend/test_multi_alpha_workbench.cjs`
- `npm run build:results-workbench`

### Unified Runtime Smoke

真实 smoke 已通过：

- `exp_20260326_063352953_1cb8`

关键事实：

- `run_meta.data.asset_role = unified_multi_sleeve_combo`
- `stage_pipeline.execution_shell = unified_combo_phase1`
- `combo_components.stock_component.exp_id` 存在
- `combo_components.etf_component.exp_id` 存在
- `audit.gates.unified_runtime_completeness = PASS`
- `audit.gates.attribution_traceability = PASS`

### Single-Sleeve Regression

ETF 单独运行未被破坏：

- 历史参考：`exp_20260325_050959295_5c74`
- 当前重跑：`exp_20260326_063524651_0189`

核心指标完全一致：

- `total_return`
- `cagr`
- `sharpe`
- `max_drawdown`
- `trades`
- `turnover`

A 股 baseline 回归：

- baseline：`exp_20260322_004509956_135e`
- rerun：`exp_20260326_063707607_d61b`

结论：

- `perf / nav / portfolio_daily` 无行为漂移
- `portfolio_trades` 仅 `meta_json` 发生变化，核心列完全一致
- 剩余 diff 属于 additive enrichment：
  - `run_meta.data.benchmark_source`
  - `manifest.artifacts.attribution_audit`
  - `run_config_behavior_hash`

当前没有发现新的未解释行为漂移。

## Residual Risks

- unified combo 当前仍是 Phase 1：
  - 默认等权 `50/50`
  - 不是正式最优配比结论
- `execution_realism` 与 `reproducibility` gate 仍有既有问题，不是本轮 unified runtime 特有问题
- 组合结果当前成立于 A 股个股 + ETF 两腿；防守层与保险层不在本轮范围内

## Rollback

如果需要回退 unified runtime 入口，核心撤回这些文件即可：

- `backend/core/services/cn_stock_etf_unified_runtime_service.py`
- `backend/core/audit/research_audit.py`
- `frontend/app/results-workbench/helpers/resultsFormatting.js`
- `frontend/app/results-workbench/App.vue`
- `frontend/app/results-workbench/components/ResearchComboPanel.vue`
- `frontend/app/results-workbench/components/ResearchComboChart.vue`

然后把前端入口退回旧的 research combo 模板语义。
