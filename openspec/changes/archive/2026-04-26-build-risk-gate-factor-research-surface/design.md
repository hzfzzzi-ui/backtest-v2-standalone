## Context

当前主线 `signal_composition` 明确包含 `Risk Gate`，角色是 `Soft Weight`，但它对应的真实逻辑并没有独立 catalog。现状上，主线里与 Risk Gate 高度相关的条件分散在：

- benchmark regime / breakout_buy_allowed
- breakout quality pass / breakout margin
- bull breakout quality veto
- 部分 residual/quality/sector 上下文
- 候选计划中的 score-weight/soft-weight 路径

这意味着当前研究层无法独立回答：
- 哪些样本是被 Risk Gate 惩罚的
- 哪些 veto 是主要贡献者
- Risk Gate 更像 rank、context 还是 veto

## Goals / Non-Goals

**Goals:**
- 建立研究层独立的 risk gate factor catalog。
- 生成可审计的 risk gate snapshots 与 factor score snapshots。
- 通过 `study_run` 提供正式的 risk gate factor 研究入口。
- 保持与当前主线真实语义对齐，但不改变主线行为。

**Non-Goals:**
- 不在这条 change 里改 runtime。
- 不把 Risk Gate 默认接成正式 veto/rank/weight 策略逻辑。
- 不在这条 change 里同时拆 `final_score` 或 `breakout failure/exit risk`。

## Decisions

### D1. 首版只做研究层，不碰 runtime
- 选择：沿用前面 factor/state/moneyflow 的平台路径，只新增 risk gate 的 catalog/snapshot/study surface。
- 原因：先把主线隐含逻辑变成可研究对象，再决定是否要回接策略。
- 备选：直接改主线 Risk Gate 逻辑。未选，因为当前还缺少清晰研究口径。

### D2. 首版只收“与当前主线真实交易相关”的 Risk Gate 成分
- 选择：catalog 首版优先覆盖当前主线里最明确的 risk gate 相关字段，如 benchmark gate、breakout quality pass、bull quality veto、risk gate soft-weight context。
- 原因：先贴近主线真实行为，不先发明额外理论因子。
- 备选：一次性把所有 exit / lifecycle 风险都并入 Risk Gate。未选，因为边界会失控。

### D3. Risk Gate 首版按 `context/veto` 研究，不按正向 rank 预设
- 选择：study surface 默认支持单因子、组合分、bucket veto 和条件分布研究。
- 原因：Risk Gate 更可能是条件因子或 veto 因子，不应预设成 `higher is better` 排序因子。
- 备选：直接按 IC rank 因子研究。未选，因为这会再次混淆因子角色。

## Risks / Trade-offs

- [风险] Risk Gate 的边界可能和 `final_score` 重叠。→ 首版要求 catalog 必须区分“直接 gate/veto”与“综合排序结果”。
- [风险] 研究定义脱离主线真实语义。→ 首版只收当前主线已明确消费的 gate/veto 条件，不扩展到新逻辑。
- [风险] 用户误把研究 surface 当 runtime 能力。→ 在 spec 和输出中明确 `RESEARCH_ONLY`。
