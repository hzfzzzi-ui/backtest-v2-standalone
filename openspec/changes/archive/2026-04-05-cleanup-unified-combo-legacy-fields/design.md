# Design

## Scope

这轮 cleanup 只清理 unified combo 合同边界内已经被正式替代的 legacy 字段，不动其他不相关的历史命名。

## Decisions

### 1. replay anchor baseline 直接迁到 contract-only

`A_STOCK_ETF_V1` source wrapper 升级为：

- `unified_runtime.component_source_contract`
- `unified_runtime.combo_context.component_source_contract`

并删除：

- `unified_runtime.sleeves`
- `unified_runtime.combo_context.combo_components`
- `unified_runtime.combo_context.component_source_mode`

### 2. 新运行产物不再并列输出 legacy 来源字段

`run_meta.json` 继续保留：

- `component_source_contract`
- `combo_context`
- `combo_runtime`
- `research_combo`

但不再输出：

- `combo_components`
- `combo_runtime.component_source_mode`
- `research_combo.component_source_mode`
- `combo_context.component_source_mode`

组件实验引用统一从 `config.json.component_experiments` 读取。

### 3. 结果工作台删除 legacy component warmup shim

`combo_truth` 已经是正式 surface 子面。桌面壳不再 direct load component sections，也不再把 legacy artifacts 拼成 snapshot。

## Validation

- 后端重跑 `A_STOCK_ETF_V1`
- 核对 `cagr = 0.13307783712519594`
- 核对新 `input_config.json` / `run_config.json` / `run_meta.json` 不再出现已清理字段
