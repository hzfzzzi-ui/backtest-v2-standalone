## Context

当前主线的 `_final_score` 是真实排序核心，但它的组成分散在 breakout precompute 与 day signal provider 中，常见字段包括：

- `_residual_strength_score`
- `_sector_strength_score`
- `_volume_price_quality_score`
- `_breakout_quality_score`
- `_breakout_margin_score`
- `conditional_*`
- `industry_second_stage_*`
- `_final_score`

研究层如果只看少数原子因子，会误把“未拆干净的综合分”当成“主线因子失效”。因此需要先把 `final_score` 的真实组成拆出来，并以研究层快照方式沉淀。

## Goals / Non-Goals

**Goals:**
- 建立研究层独立的 final score composition catalog。
- 生成可审计的 final score composition snapshots 与 factor score snapshots。
- 通过 `study_run` 提供正式的 final score composition 研究入口。
- 保持与当前主线真实 `final_score` 组成语义对齐，但不改变主线行为。

**Non-Goals:**
- 不在这条 change 里改 runtime 排序。
- 不把 `final_score` 默认拆成新的正式交易 rank。
- 不在这条 change 里同时拆 `Risk Gate` 或 `breakout failure / exit risk`。

## Decisions

### D1. 首版只做研究层，不碰 runtime
- 选择：沿用前面 factor/state/moneyflow/risk-gate 的平台路径，只新增 final score composition 的 catalog/snapshot/study surface。
- 原因：先把主线真实排序组成变成可研究对象，再决定是否要回接策略。
- 备选：直接重写主线排序逻辑。未选，因为当前还缺少清晰研究口径。

### D2. 首版只收“当前主线真实用于 `_final_score` 的组成项”
- 选择：catalog 首版优先覆盖当前主线里最明确的 `final_score` 组成字段，如 residual/sector/volume-price/breakout quality/breakout margin/conditional/industry second-stage。
- 原因：先贴近主线真实行为，不先发明额外理论因子。
- 备选：一次性把所有候选计划与执行层派生字段都并入。未选，因为边界会失控。

### D3. 研究时同时保留“原子组成项”和“总分”
- 选择：study surface 默认支持单组成项研究、组合分研究和贡献拆解。
- 原因：既要看原子项方向，也要看 `_final_score` 整体是否存在研究面解释力。
- 备选：只研究 `_final_score` 总分。未选，因为这会丢失拆分价值。

## Risks / Trade-offs

- [风险] 组成项与 Risk Gate 边界重叠。→ 首版要求 catalog 标明“直接组成项”和“条件上下文”。
- [风险] 原子字段过多导致 catalog 失控。→ 首版只收当前主线已明确暴露的核心组成项。
- [风险] 用户误把研究 surface 当 runtime 重构完成。→ 在 spec 和输出中明确 `RESEARCH_ONLY`。
