## Why

现在 `component_source_contract` 已经成为前端结果工作台、unified combo 编译入口和 unified combo 运行服务的主消费入口，legacy `research_custom_sleeves` 与 `unified_runtime.sleeves[*]` 已经退为 fallback。继续长期保留 fallback 会让主路径合同收口停在“半完成态”，并给后续维护留下双入口复杂度。

下一步需要在 replay anchor 继续稳定的前提下，把 unified combo 主运行路径正式切到 contract-only，删除 legacy fallback 消费逻辑，使 `research_custom_sleeves` 不再参与主运行编译入口。

## What Changes

- 删除 unified combo 编译路径对 legacy `unified_runtime.sleeves[*]` 的主路径消费，只保留 `component_source_contract`。
- 删除 unified combo 运行服务对 legacy `sleeves[*].semantic_config/runtime_config` 的 fallback 消费。
- 收紧前端与产物口径，明确 `research_custom_sleeves` 只保留历史 provenance，不再承担当前主运行职责。
- 保持 `A_STOCK_ETF_V1` replay anchor 不变，作为删 fallback 的唯一验收门槛。

## Capabilities

### New Capabilities
- `unified-combo-contract-only-runtime`: 定义 unified combo 仅通过 `component_source_contract` 运行的正式边界

### Modified Capabilities
- `runtime-boundary-contracts`: unified combo 主运行边界从 contract-first+fallback 收紧为 contract-only
- `post-refactor-residual-cleanup`: 删除 fallback 前后的回放锚点审计与回退要求

## Impact

- 后端编译入口：`backend/api/backtest_v2/runner_config_bundle.py`
- unified combo 运行服务：`backend/core/services/cn_stock_etf_unified_runtime_service.py`
- 前端结果工作台与组合展示口径
- cleanup 审计与 runtime boundary 主 spec
