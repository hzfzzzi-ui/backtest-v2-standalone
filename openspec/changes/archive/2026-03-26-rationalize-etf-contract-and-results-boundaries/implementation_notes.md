# 实现说明

## 结论

本次 change 已完成三件事：

1. 将 ETF beta 的配置归一化、运行时摘要和下游投影收口到单一 contract owner。
2. 将 research combo 的结果真相继续下沉到后端 surface / snapshot，前端不再拼装伪 snapshot 作为正式解释来源。
3. 收紧旧桌面壳与 Vue workbench 的 owner boundary，保留兼容层，但停止其继续承担核心研究语义重算。

本轮不改 baseline 主逻辑、不新增 ETF 规则族，也不实现 unified runtime。

## 主要改动

### 1. ETF contract owner 收口

新增 ETF contract owner：

- [etf_beta_contract.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py)

将 ETF 默认合同、归一化、暴露语义、phase1 summary、runtime 选择抽取为统一 owner，并在下游复用：

- [cn_a_governed_mainline.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/cn_a_governed_mainline.py)
- [cn_etf_beta_signal_provider.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py)
- [daily_accounting.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/adapters/daily_accounting.py)
- [research_audit.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)
- [data_bundle_builder.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/tools/data_bundle_builder.py)
- [artifacts_finalize.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/artifacts_finalize.py)

兼容性保留：

- `run_meta["etf_beta"]["vol_target"]`
- `run_meta["etf_beta"]["sleeve_budget_used"]`

同时保留新的：

- `runtime_vol_target`
- `sleeve_budget_snapshot`

这样可以在不打断现有下游的前提下完成 owner 收口。

### 2. 后端 combo truth surface

新增并下沉 research combo 的 canonical truth surface：

- [experiment_query_service.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/services/experiment_query_service.py)

新增 `combo_truth` section，用于返回：

- 组合展示摘要
- stock / etf 组件实验 id
- 组件 snapshot 真相

前端通过该 surface 直接消费 research combo 真相，不再从组件产物拼装伪统一快照。

### 3. 前端 owner boundary 收紧

旧壳仍保留 bootstrap / chrome / bridge 职责，但不再作为结果真相 owner：

- [artifacts.js](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/artifacts.js)
- [backtest_v2.js](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/backtest_v2.js)

Vue workbench 改为优先消费后端 combo truth：

- [App.vue](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/app/results-workbench/App.vue)
- [ResearchComboChart.vue](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/app/results-workbench/components/ResearchComboChart.vue)
- [resultsFormatting.js](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/app/results-workbench/helpers/resultsFormatting.js)

旧的前端组合重算逻辑改为显式 legacy shim，不再作为活跃 owner。

## 风险

1. 这轮只收边界，不做 unified runtime，所以 research combo 仍是只读组合结果，不是正式统一执行组合。
2. ETF contract owner 收口时必须保留旧字段别名，否则既有 artifact / audit / 前端会回归。
3. 旧壳减重后，若某些历史实验只依赖客户端补算，前端会显示显式空态，而不是继续隐式重算。

## 验证

已通过：

```bash
pytest tests/unit/test_research_audit_contract.py tests/unit/test_artifacts_finalize_regime_meta.py tests/unit/test_semantic_config_compiler.py tests/unit/test_cn_etf_beta_signal_provider.py -q
pytest tests/unit/test_experiment_query_service.py tests/unit/test_frontend_owner_boundaries.py -q
node --test tests/frontend/test_results_workbench_multi_alpha.mjs tests/frontend/test_multi_alpha_workbench.cjs
npm run build:results-workbench
openspec validate rationalize-etf-contract-and-results-boundaries --type change --strict
```

关键验证点：

- ETF summary 仍输出兼容字段。
- backend `combo_truth` section 可直接供前端消费。
- 前端不再把组合结果真相建立在客户端拼装 snapshot 上。
- 旧壳中重复活跃 helper 已被压缩为单 owner / legacy shim。

## 回退

若要回退本轮 change，优先按以下顺序撤回：

1. ETF contract owner 收口：
   - [etf_beta_contract.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py)
   - [cn_a_governed_mainline.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/cn_a_governed_mainline.py)
   - [cn_etf_beta_signal_provider.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py)
   - [daily_accounting.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/adapters/daily_accounting.py)
   - [research_audit.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)
   - [data_bundle_builder.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/tools/data_bundle_builder.py)
   - [artifacts_finalize.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/artifacts_finalize.py)

2. combo truth surface：
   - [experiment_query_service.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/services/experiment_query_service.py)

3. 前端 owner boundary：
   - [artifacts.js](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/artifacts.js)
   - [backtest_v2.js](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/backtest_v2.js)
   - [App.vue](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/app/results-workbench/App.vue)
   - [ResearchComboChart.vue](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/app/results-workbench/components/ResearchComboChart.vue)
   - [resultsFormatting.js](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/app/results-workbench/helpers/resultsFormatting.js)

若只需恢复旧兼容口径，可先保留 `combo_truth`，仅恢复前端 legacy fallback。
