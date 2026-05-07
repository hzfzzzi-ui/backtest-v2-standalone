## Context

当前 moneyflow 研究已经表明，`monthly_divergence_rate` 在研究面上是正向候选因子，并且在 `BULL` 内部的解释力更强。但上一轮把它直接接成日频 `veto` 后，股票腿基线明显变差，说明这条因子不适合作为候选硬过滤器。现有 runtime 已支持 `tiebreak` 模式，因此本次最小改动只增加一个 `BULL-only` gating，让 tiebreak 只在 `effective_state_5 == BULL` 时生效，并补充诊断字段以便审计。

## Goals / Non-Goals

**Goals:**
- 为 moneyflow overlay 增加一个研究态 `bull_only_tiebreak` 行为。
- 仅在 `BULL` 状态内，对已有候选做 moneyflow tiebreak。
- 保持主排序、退出、ETF / defense 和非 `BULL` 日子的候选计划行为不变。
- 让实验产物可确认 overlay 是否启用、是否因非 `BULL` 被抑制。

**Non-Goals:**
- 不重写 moneyflow overlay 评分逻辑。
- 不把 `monthly_divergence_rate` 接成主排序或 soft weight。
- 不修改正式主线默认值。
- 不把 `BULL-only` gating 扩展到 ETF、defense 或组合层。

## Decisions

### 1. 复用现有 overlay 管道，只增加一个 `bull_only_tiebreak` 模式
- 选择：在现有 moneyflow overlay mode 里新增研究态模式，而不是再造独立的 context/gate 配置。
- 原因：最小改动、最容易和已有 `tiebreak` / `veto` A/B 对齐。
- 备选方案：新增独立 `only_in_bull` 布尔配置。放弃原因是会让配置合同继续分叉。

### 2. `BULL` 判定以日度 `effective_state_5` 为单一真相
- 选择：直接使用候选计划当日已经可见的状态字段，不引入第二套 benchmark/regime 判定。
- 原因：避免口径漂移，保持与当前股票腿 runtime 完全一致。
- 备选方案：单独重算 benchmark regime。放弃原因是会制造第二真相。

### 3. 非 `BULL` 日子退化为 overlay 关闭，而不是退化为普通 `tiebreak`
- 选择：`bull_only_tiebreak` 在非 `BULL` 日子完全不生效。
- 原因：实验目标是隔离 `BULL` context 角色；如果在非 `BULL` 仍做普通 tiebreak，就无法归因。
- 备选方案：非 `BULL` 日子回退到普通 `tiebreak`。放弃原因是会把两个实验混在一起。

### 4. 补充最小诊断字段，不扩 schema 主体
- 选择：仅在 debug/diagnostic 输出里增加 `moneyflow_overlay_bull_only`、`moneyflow_overlay_bull_gate_on` 之类字段。
- 原因：实验需要审计，但不值得为一次研究扩展更大的产物合同。

## Risks / Trade-offs

- [风险] `BULL` 状态字段若在候选计划层不可用，会导致 gating 落空。 → [缓解] 先用最小单测覆盖 `BULL` / 非 `BULL` 分支。
- [风险] tiebreak 作用面太小，实验可能接上但结果接近零。 → [缓解] 同时输出启用天数和 gate_on 天数，确认不是假阴性。
- [风险] `BULL-only` 即使研究面正确，策略面仍可能失败。 → [缓解] 明确把本次结论限定为“这版接法是否成立”，不外推到因子本身。
- [风险] 诊断字段若只在 debug plan 存在，最终 CSV 仍可能不完整。 → [缓解] 先保证日级聚合诊断可见，候选级审计不足作为已知限制记录在 notes 中。
