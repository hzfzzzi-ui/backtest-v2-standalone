# cleanup-unified-combo-legacy-fields

## Why

unified combo 已经完成 `contract_only` 主路径收口，但代码和产物里仍残留一批不再需要的 legacy 来源字段：

- `unified_runtime.sleeves[*].semantic_config/runtime_config`
- `combo_components`
- 并列 `component_source_mode`
- 旧桌面壳的 component warmup shim

这些字段会继续制造双轨语义，和当前文档中“`component_source_contract` 是正式来源合同，legacy 仅可作为历史 provenance”的口径不一致。

## What Changes

- 迁移 `A_STOCK_ETF_V1` replay anchor baseline 到 contract-only source wrapper。
- 删除 unified combo 编译与运行产物里不再需要的 legacy 来源字段。
- 删除 surface / 审计 / 前端结果桥接里对这些旧字段的主路径消费。
- 保持 replay 结果继续对齐 `exp_20260404_074403089_e18e`。

## Impact

- 新生成的 unified combo 产物不再写出 `combo_components` / 并列 `component_source_mode` / `unified_runtime.sleeves`。
- 组件实验引用改由 `config.component_experiments` 提供真相。
- 旧桌面壳不再自行 warmup research combo component artifacts。
