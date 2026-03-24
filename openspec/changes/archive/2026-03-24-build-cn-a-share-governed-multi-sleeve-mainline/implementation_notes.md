# Implementation Notes

## 完成范围

本 change 已完成 Phase 1 的 contract 收敛与最小实现，覆盖：

- `market_regime_engine` 的 `base/effective state`、subscores、manual override 占位与状态审计输出
- `global_portfolio_governor` 的 `total_risk_budget / total_exposure_cap / sleeve_budgets / drawdown ladder / defense floor / budget reason codes`
- `baseline_V10.1 -> cn_stock_trend_alpha_core` 的正式语义重定位
- `cn_etf_beta` Phase 1 的 core beta + limited defense candidate 接入
- `attribution_audit` 的 `state/budget/sleeve/manual_override` 统一归因产物

## 定向验证

### 自动化覆盖

已通过的定向测试包括但不限于：

- `tests/unit/test_bridge_adapter_route_control.py`
- `tests/unit/test_bridge_adapter_accounting.py`
- `tests/unit/test_experiment_runner_daily_schema.py`
- `tests/unit/test_experiment_runner_multi_alpha_compile.py`
- `tests/unit/test_multi_alpha_order_planning.py`
- `tests/unit/test_data_bundle_builder.py`
- `tests/unit/test_artifacts_finalize_regime_meta.py`
- `tests/unit/test_research_audit_contract.py`
- `tests/unit/test_semantic_config_compiler.py`
- `tests/unit/test_attribution_audit.py`

同时已通过：

- `node --test tests/frontend/test_multi_alpha_workbench.cjs`
- `openspec validate build-cn-a-share-governed-multi-sleeve-mainline --type change --strict`

### A 股主线最小回归

采用同口径 `baseline_V10.1` workbench 配置做容器内 smoke 回归：

- 参考实验：`exp_20260322_004509956_135e`
- 新实验：`exp_20260324_045411088_5c05`

核心绩效完全一致：

- `total_return`: `0.9095217321584999 -> 0.9095217321584999`
- `cagr`: `0.15429757211200124 -> 0.15429757211200124`
- `max_drawdown`: `-0.2905981811162982 -> -0.2905981811162982`
- `sharpe`: `0.7248717491747954 -> 0.7248717491747954`
- `trades`: `246 -> 246`
- `turnover`: `0.017866507177685252 -> 0.017866507177685252`

结论：本 change 在 A 股股票主线上的影响是 **contract/产物层收敛**，没有引入未解释的主行为漂移。

## 产物层新增事实

新实验 `exp_20260324_045411088_5c05` 中已出现：

- `run_meta.governed_snapshot`
- `run_meta.attribution`
- `run_meta.report_consistency.stock_alpha_core_budget_semantics`
- `audit.attribution_audit`

其中 A 股主线的 budget consumer 已明确收敛为：

- `asset_scope = cn_a_equity`
- `budget_consumer_sleeve_id = cn_stock_trend_alpha_core`
- `budget_consumer_system_role = stock_alpha_sleeve`
- `stock_alpha_core_budget_semantics = consume_governor_sleeve_budget`
- `stock_alpha_core_total_budget_owner = global_portfolio_governor`

## 回退策略

本 change 的回退应按“先隐藏新 contract 暴露面，再撤回聚合逻辑，最后撤回新增模块”的顺序执行。

### 1. 最小回退：仅关闭新暴露面

若问题只在产物兼容层，优先撤回以下输出层改动：

- `backend/api/backtest_v2/artifacts_finalize.py`
- `backend/core/tools/experiment_runner.py`
- `backend/core/stage_pipeline/adapters/result_bridge.py`

效果：

- 关闭 `run_meta.governed_snapshot`
- 关闭 `run_meta.attribution`
- 关闭 `audit.attribution_audit`
- 保留现有股票/ETF 真值表和主交易逻辑不变

### 2. 中等回退：撤回 Governor 聚合 contract

若问题出在预算摘要或 snapshot 语义，继续撤回：

- `backend/core/stage_pipeline/adapters/day_controls.py`
- `backend/core/stage_pipeline/adapters/daily_accounting.py`
- `backend/core/config/cn_a_governed_mainline.py`

效果：

- 关闭 `governor_budget_json`
- 回退 `total_risk_budget / total_exposure_cap / sleeve_budgets` 摘要
- 保留原有局部预算与交易行为

### 3. 完整回退：撤回 Phase 1 新能力

若需要整体回到 change 前状态，再撤回：

- `backend/core/audit/attribution_audit.py`
- `backend/core/audit/research_audit.py`
- `backend/core/tools/data_bundle_builder.py`
- `backend/core/stage_pipeline/adapters/order_planning.py`
- `backend/api/backtest_v2/semantic_config_schema.py`
- `backend/api/backtest_v2/protocol.py`

效果：

- 撤回 `cn_stock_trend_alpha_core` / `cn_etf_beta` / `attribution_audit` 的新增 contract 暴露
- 保留现有股票 `V2 canonical` 与 ETF 真值表，不做数据层回滚

## 明确保留不回滚的部分

本 change 不涉及数据库 schema 变更，也不要求回滚以下数据资产：

- A 股股票 `V2 canonical`
- ETF 真值表 `pams_cn_etf_daily`
- ETF 目录/coverage 数据

它们应继续保留，回退只针对 runtime contract、snapshot 暴露面与审计聚合逻辑。
