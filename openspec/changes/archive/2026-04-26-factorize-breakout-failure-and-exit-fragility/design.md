## Context

当前主线里与失败风险和退出脆弱性高度相关的逻辑分散在：

- `pre_profit_breakout_failure`
- `low10_exit`
- `risk_off_exit`
- breakout margin / breakout quality / ATR context
- 持仓生命周期中的 early fade / weak carry / break-floor 等上下文

这意味着当前研究层无法独立回答：
- 哪类 entry context 最容易走向 breakout failure
- 哪类持仓最容易触发脆弱退出
- exit 规则到底是在剔除坏仓，还是在误杀好仓

## Goals / Non-Goals

**Goals:**
- 建立研究层独立的 breakout failure / exit fragility factor catalog。
- 生成可审计的 breakout failure / exit fragility snapshots 与 factor score snapshots。
- 通过 `study_run` 提供正式的 breakout failure / exit fragility 研究入口。
- 保持与当前主线真实退出语义对齐，但不改变主线行为。

**Non-Goals:**
- 不在这条 change 里改 runtime exit。
- 不把 failure/fragility 因子默认接成正式 veto/rank/exit 策略逻辑。
- 不在这条 change 里同时拆 `Risk Gate` 或 `final_score`。

## Decisions

### D1. 首版只做研究层，不碰 runtime exit
- 选择：沿用前面 factor/state/moneyflow/risk-gate/final-score 的平台路径，只新增 breakout failure / exit fragility 的 catalog/snapshot/study surface。
- 原因：先把主线隐含的失败/脆弱性逻辑变成可研究对象，再决定是否要回接策略。
- 备选：直接改 exit 规则。未选，因为当前还缺少清晰研究口径。

### D2. 首版只收“与当前主线真实失败/退出相关”的上下文
- 选择：catalog 首版优先覆盖当前主线里最明确的失败风险字段，如 breakout margin/quality/ATR/fade/break-floor/exit reason context。
- 原因：先贴近主线真实行为，不先发明额外理论因子。
- 备选：一次性把所有生命周期事件都并入。未选，因为边界会失控。

### D3. 首版按 `failure-risk/context` 研究，不按正向 rank 预设
- 选择：study surface 默认支持 failure bucket、fragility bucket、exit-conditional 分布研究。
- 原因：这类因子更可能是失败风险或 veto 因子，不应预设成 `higher is better` 排序因子。
- 备选：直接按 IC rank 因子研究。未选，因为这会再次混淆因子角色。

## Risks / Trade-offs

- [风险] fragility 因子与 Risk Gate 边界重叠。→ 首版要求 catalog 明确区分“失败风险”与“参与门控”。
- [风险] 退出上下文依赖持仓生命周期，快照口径容易漂。→ 首版要求快照绑定 baseline 和 as-of 语义。
- [风险] 用户误把研究 surface 当 exit 重构完成。→ 在 spec 和输出中明确 `RESEARCH_ONLY`。
