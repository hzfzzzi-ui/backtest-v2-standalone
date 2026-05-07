## Context

当前 unified combo 存在两个同时成立的事实：
1. `research_custom_sleeves` 仍承担真实 baseline 回放职责，删除它会直接破坏 `A_STOCK_ETF_V1` 的正确目标版本。
2. 它又不是正式共享执行合同，因为 execution kernel、正式审计与正式 runtime boundary 都不应依赖研究型 provenance 字段做主语义判断。

2026-04-04 的修复证明，真正需要保护的是回放锚点与 sleeve-local asset scope，而不是把所有过渡字段一次性清空。基于这个事实，本 change 的第一阶段应优先补出显式合同对象，让系统能同时表达“正式字段集合”和“当前仍在过渡”。

## Goals / Non-Goals

**Goals:**
- 给 unified combo 增加显式的 component source contract 元数据对象。
- 保持 `A_STOCK_ETF_V1` 当前目标版本与回放结果不变。
- 让编译结果与运行产物都能稳定输出该合同对象，供后续 cleanup 审计与前端消费。
- 明确区分正式 source contract 与 `research_custom_sleeves` provenance。

**Non-Goals:**
- 本 change 第一阶段不删除 `research_custom_sleeves`。
- 本 change 第一阶段不把 unified combo 改造成正式多 sleeve execution runtime。
- 本 change 第一阶段不改动 stock/ETF 子腿的研究逻辑、权重公式或收益口径。
- 本 change 第一阶段不强制前端切换到新字段作为唯一展示入口。

## Decisions

### 决策 1：先增加显式合同对象，不直接删除旧 provenance
- 方案 A：直接删除 `research_custom_sleeves`，强制切到 `official_sleeve_anchors`
- 方案 B：保留现有回放语义，同时增加显式合同对象，标明 `transitional=true`
- 选择：方案 B
- 原因：方案 A 已被证明会把系统锁到错误目标版本；方案 B 可以先把合同立住，再逐步迁移消费方。

### 决策 2：合同对象挂在 unified combo 编译结果与运行产物上
- 合同对象应同时出现在编译阶段和运行产物阶段，避免前后端、审计与 cleanup 各自重新推断。
- 第一阶段优先挂在 `combo_context` / `combo_runtime` 附近，减少扩散到更多模块的改动量。

### 决策 3：合同对象只描述来源，不承载 execution 语义
- 新对象只包含组件来源、模式、过渡状态和 replay anchor 相关信息。
- 不把 execution kernel 需要的正式输入、风险覆盖或 target book 语义塞进这个对象里。

## Risks / Trade-offs

- [风险] 新增合同对象后，旧字段和新字段会短期并存 -> 缓解：显式标注 `transitional`，并在 spec 中写清旧字段只作 provenance。
- [风险] 开发者误把新对象当成 execution 主合同 -> 缓解：spec 中明确它不进入 `action_intent_v1 / risk_override_v1 / target_book_v1`。
- [风险] 未来 cleanup 过早删除旧链路 -> 缓解：把 `e18e/532d/8491` 回放锚点写入 cleanup gate。
- [风险] 运行产物与编译结果字段不一致 -> 缓解：第一阶段只在 unified combo 的单一路径中生成并透传相同对象。
