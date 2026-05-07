## Why

当前 unified combo 虽然已经有了显式的 `component_source_contract`，但前端结果工作台仍优先读取旧的 `combo_components` / `component_source_mode` 字段，后端 unified combo 的实际运行消费也仍然直接依赖 `unified_runtime.sleeves[*].semantic_config/runtime_config`。这意味着新合同对象已经存在，却还没有真正成为主消费入口。

现在需要把 `component_source_contract` 从“仅产物可见”推进到“前端优先消费、后端优先消费”，让 `research_custom_sleeves` 真正降级为 fallback，而不是继续充当主运行编译入口。

## What Changes

- 前端结果工作台改为优先读取 `component_source_contract` 的 `source_mode` 与 `components`。
- unified combo 编译路径改为优先从 `component_source_contract.components[*].compile_input` 解析组件运行输入。
- unified combo 运行服务改为优先消费 `component_source_contract.components[*].compile_input`，仅在合同缺失时回退旧 `sleeves` 入口。
- 保留 `research_custom_sleeves` 作为 transitional fallback，继续保护 `A_STOCK_ETF_V1` 的正确目标版本。

## Capabilities

### New Capabilities
- `unified-combo-component-source-consumption`: 定义前端与 unified combo 运行时对 `component_source_contract` 的优先消费规则

### Modified Capabilities
- `runtime-boundary-contracts`: unified combo 组件来源合同从“可见元数据”提升为主消费入口，legacy sleeves 退为 fallback

## Impact

- 前端结果工作台：`frontend/app/results-workbench/helpers/resultsFormatting.js`、`frontend/app/results-workbench/components/ResearchComboChart.vue`
- 后端编译入口：`backend/api/backtest_v2/runner_config_bundle.py`
- unified combo 运行服务：`backend/core/services/cn_stock_etf_unified_runtime_service.py`
