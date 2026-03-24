## 实现范围

本轮已完成：

- `market_regime_engine` facade 收口，正式输出 canonical 五状态、coarse 状态、block/domain 归因、state stability、manual override 双轨 payload。
- `cn-a-portfolio-governor` 只消费正式 regime payload，不再自行猜测 canonical 状态与 override 语义。
- `cn-a-attribution-audit` 统一记录 state / budget / sleeve / manual override 证据链。
- `backtest-research-audit` 现在会同时校验：
  - `run_meta.governed_snapshot`
  - `run_meta.regime.latest_state`
  - `attribution_audit.json`
  - `regime_audit_summary.json`
- 结果工作台摘要现在直接消费 Governed A 股 snapshot，不再依赖 `market_state` / `trade_mode` 反推状态语义。

本轮刻意没有做：

- 左侧蓝筹 sleeve
- insurance overlay
- 新的情绪 / 宏观正式因子接入
- 把 `market_regime_engine` 抽成独立服务

## 关键文件

- `backend/core/engine_vector/market_regime_engine.py`
- `backend/core/engine_vector/breakout_signal_provider.py`
- `backend/core/stage_pipeline/adapters/day_controls.py`
- `backend/core/stage_pipeline/adapters/daily_accounting.py`
- `backend/core/audit/attribution_audit.py`
- `backend/core/audit/research_audit.py`
- `backend/api/backtest_v2/artifacts_finalize.py`
- `frontend/app/results-workbench/helpers/resultsFormatting.js`
- `frontend/app/results-workbench/components/ResultsOverview.vue`
- `backend/cli/managed/baseline_regression_check.py`

## 验证

已通过：

- `pytest tests/unit/test_market_regime_engine.py tests/unit/test_breakout_signal_provider.py tests/unit/test_bridge_adapter_accounting.py tests/unit/test_artifacts_finalize_regime_meta.py tests/unit/test_attribution_audit.py tests/unit/test_experiment_runner_daily_schema.py -q`
- `pytest tests/unit/test_bridge_adapter_route_control.py tests/unit/test_regime_audit.py -q`
- `pytest tests/unit/test_research_audit_contract.py tests/unit/test_baseline_regression_check.py -q`
- `node --test tests/frontend/test_results_workbench_multi_alpha.mjs`
- `openspec validate formalize-market-regime-engine-attribution-contract --type change --strict`

## A股主线最小回归

### 第一轮回归

执行：

- `python backend/cli/managed/baseline_regression_check.py --baseline-exp-id exp_20260322_004509956_135e --rerun --output-json outputs/ops/formalize_market_regime_engine_attribution_contract_20260324/baseline_compare.json`

结果：

- rerun 候选实验：`exp_20260324_074454523_9554`
- baseline compare：`FAIL`

定位出的真实问题：

- rerun 请求在 `config_source=workbench_config` 时退化成了 `runtime_config_json`
- 根因在 `baseline_regression_check._build_baseline_request(...)` 的优先级错误

修复：

- 显式保留 `workbench_config` 请求源
- 新增单测锁定这个优先级

### 第二轮回归

执行：

- `python backend/cli/managed/baseline_regression_check.py --baseline-exp-id exp_20260322_004509956_135e --rerun --output-json outputs/ops/formalize_market_regime_engine_attribution_contract_20260324/baseline_compare_after_workbench_fix.json`

结果：

- rerun 候选实验：`exp_20260324_075952284_3d70`
- baseline compare：旧 foundation contract 下仍显示 `FAIL`

但当前已确认：

- `portfolio_daily`: `PASS`
- `perf`: `PASS`
- `nav`: `PASS`
- `run_meta_core`: `PASS`
- `run_meta_universe`: `PASS`

剩余 3 个 diff 都是已解释的 additive enrichment，不是未解释行为漂移：

1. `portfolio_trades.file_hash`
   - 交易核心字段逐行一致
   - 差异只来自 `meta_json` 新增字段：
     - `bull_breakout_quality_veto_applied`
     - `bull_breakout_quality_veto_min_breakout_margin_score`
     - `bull_breakout_quality_veto_min_residual_strength_score`

2. `config_truth.run_config_behavior_hash`
   - 差异来自 `run_config.json` 的 additive contract/enrichment：
     - `asset_context.asset_family`
     - `governed_a_share`
     - `schema_mapping.pams_cn_etf_daily`
     - `strategy.params.bull_breakout_quality_veto_*`

3. `manifest.artifacts.attribution_audit`
   - 这是本轮 change 新增的正式产物暴露面

### 结论

- 本轮 `formalize-market-regime-engine-attribution-contract` 没有引入未解释的 A 股主线行为漂移。
- 初始大漂移来自 baseline rerun 请求源退化，已修复。
- 修复后剩余差异属于产物和配置 enrichment，语义可解释，未改变核心收益、回撤、交易数和日级行为。

## 回退路径

### 只关闭前端与产物暴露面

撤回：

- `frontend/app/results-workbench/helpers/resultsFormatting.js`
- `frontend/app/results-workbench/components/ResultsOverview.vue`
- `backend/api/backtest_v2/artifacts_finalize.py`

效果：

- Governor / regime / attribution 摘要不再出现在 snapshot / run_meta / 结果工作台。

### 撤回 Governor / Audit 正式消费

在上一层基础上继续撤回：

- `backend/core/audit/research_audit.py`
- `backend/core/audit/attribution_audit.py`
- `backend/core/stage_pipeline/adapters/day_controls.py`
- `backend/core/stage_pipeline/adapters/daily_accounting.py`

效果：

- Research audit 与 attribution audit 恢复到旧消费链路。

### 完整关闭新 regime facade

在前两层基础上继续撤回：

- `backend/core/engine_vector/market_regime_engine.py`
- `backend/core/engine_vector/breakout_signal_provider.py`
- `backend/core/engine_vector/breakout_provider_models.py`
- `backend/core/engine_runtime/foundation_shell.py`
- `backend/core/stage_pipeline/adapters/bridge_adapter.py`
- `backend/core/stage_pipeline/adapters/route_runtime.py`
- `backend/core/config/cn_a_governed_mainline.py`

效果：

- 新正式 regime payload、双轨 override、canonical 五状态 facade 整体下线。
