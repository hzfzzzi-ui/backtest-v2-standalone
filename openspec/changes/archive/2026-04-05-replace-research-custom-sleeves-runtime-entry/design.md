## Context

上一轮 change 已经证明：
1. `component_source_contract` 可以在不改变收益口径的前提下稳定出现在 `run_meta` 中。
2. 正确目标版本仍然是 `A_STOCK_ETF_V1 -> e18e` 这一组语义。
3. 但如果前端和运行时继续优先消费旧字段，新合同对象就只是“写出来了”，还没有真正接管边界。

因此这轮 change 的重点不是再改收益公式，而是把主消费优先级切到 `component_source_contract`，同时保留旧入口作为 fallback，避免再次破坏 replay anchor。

## Goals / Non-Goals

**Goals:**
- 前端结果工作台优先读取 `component_source_contract`。
- unified combo 编译与运行优先从 `component_source_contract.components[*].compile_input` 取输入。
- 保持 `A_STOCK_ETF_V1` 结果不变。

**Non-Goals:**
- 本轮不删除 `research_custom_sleeves`。
- 本轮不删除 `unified_runtime.sleeves`。
- 本轮不改 stock/ETF 研究逻辑与组合权重。

## Decisions

### 决策 1：消费优先级切换为 contract-first, legacy-fallback
- 前端先看 `component_source_contract`，再回退旧字段。
- 后端编译与运行先看 `component_source_contract.components[*].compile_input`，再回退旧 `sleeves[*]`。
- 这样可以在不破坏现有 baseline 文件的情况下完成入口替换。

### 决策 2：contract 中补足 compile_input
- 仅有 source summary 不足以真正替换运行编译入口。
- 因此合同对象中的 `components[*]` 需要携带 `compile_input.semantic_config` 与 `compile_input.runtime_config`。

## Risks / Trade-offs

- [风险] 前端消费切换后展示字段与旧逻辑不一致 -> 缓解：合同字段与旧字段短期并存，优先读取但不移除旧字段。
- [风险] 运行时优先级切换导致目标版本漂移 -> 缓解：后端与前端都重跑 `A_STOCK_ETF_V1` 对齐 `0.13307783712519594`。
- [风险] 合同中 `compile_input` 体积变大 -> 缓解：当前只限 unified combo 研究链路使用，不扩散到 execution formal contract。
