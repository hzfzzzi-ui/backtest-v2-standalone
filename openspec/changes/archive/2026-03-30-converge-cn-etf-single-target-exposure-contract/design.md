## Context

当前 formal ETF Phase 1 的 target contract 已经出现明确漂移。独立审计显示，同一实验 [exp_20260328_024314957_8f44](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260328_024314957_8f44) 中：

- [portfolio_daily.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260328_024314957_8f44/portfolio_daily.csv) / `audit.json` 记录的 `etf_target_exposure` 平均值是 `0.1038`
- 但 [orders.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260328_024314957_8f44/orders.csv) 的 BUY meta 在 `BULL` 月末大量写入 `requested_budget = 1.8`、`target_exposure = 1.8`
- 同一时间真实持仓暴露 `avg_actual_exposure = 0.3444`

这说明系统里只有一套真实持仓，但同时存在两套“目标仓位”语义：

- Governor notional cap 语义：`0.2 / 0.1 / 0.0`
- provider / execution risk-budget 语义：`1.8 / 0.1 / ...`

两条链被混用后，`research_audit` 与执行层不再共享同一个 target。继续研究 `CAGR`、部署效率或 `RISK_OFF` 行为会失真，因此需要先把 ETF 的目标仓位合同收敛成唯一真相。

## Goals / Non-Goals

**Goals:**

- 为 formal ETF Phase 1 定义单一的目标仓位真相，统一为已批准的 notional exposure，占 `NAV` 的比例。
- 要求 provider、order sizing、daily accounting、研究诊断和审计全部消费并回写同一份目标仓位值。
- 要求任何解释性 risk multiplier 或 provisional budget 不再冒充 `target_exposure`。
- 为后续回归提供硬约束：同一决策日里，orders 与 daily/audit 不得再出现 target 含义分叉。

**Non-Goals:**

- 不修改 Governor 的 denominator、`hard_max_positions` 公式或 ETF sleeve budget policy。
- 不修改 ETF 的资产池、三桶模板、正式状态映射或 `controlled_accumulation` 研究范围。
- 不解决月频 rebalance 导致的 `actual_exposure` 与 `target_exposure` 时点差异。
- 不在本 change 中追求 `CAGR` 提升或优化交易数量。

## Decisions

### 决策 1：formal ETF 只保留一套执行级目标仓位真相

选择：

- formal ETF Phase 1 只允许存在一份执行级 `target_exposure`。
- 该值表示 ETF sleeve 当天被批准并应被执行的 notional exposure，占 `NAV` 的比例。
- 该值必须同时成为 order sizing、`portfolio_daily.csv`、`rebalance_day_summary.csv` 和 `research_audit` 的目标来源。

原因：

- 这符合原始 ETF 文档里“Governor 先给 sleeve 总预算，ETF 在预算内分三桶”的语义。
- 只有这样，审计输出与实际执行目标才可对账。

备选但不采用：

- 继续保留 Governor target 与 execution target 两套字段并存。
  - 否决原因：这会继续允许同名不同义，无法根治当前漂移。

### 决策 2：任何大于 1 的 risk multiplier 只能作为解释性证据存在

选择：

- `risk_budget_multiplier`、legacy `source_risk_budget_arr`、provisional slot fallback 等量只允许作为解释性字段或 reason code 输出。
- 它们 SHALL NOT 被写入 `target_exposure`、`requested_budget`、`applied_budget`，也不得进入 `target_exposure_per_symbol` 的 sizing 链。

原因：

- `target_exposure` 的量纲必须是 `NAV` 占比；`1.8` 这类 multiplier 不是仓位目标。
- 只要 multiplier 能继续流入 execution meta，下单仍会和日终审计错位。

备选但不采用：

- 维持 multiplier 进入 provider，再在 order 层临时 clamp 到 `<= 1.0`。
  - 否决原因：这会保留中间层双口径，产物仍不一致，问题只被推迟。

### 决策 3：下单 sizing 只允许消费统一 notional target

选择：

- ETF BUY signal meta 中的 `target_exposure_per_symbol` 必须由唯一 `target_exposure` 推导。
- 若统一 target 缺失、超过 `1.0` 或与 artifact contract 不一致，系统应将其视为合同失败而不是静默回退。

原因：

- order sizing 是当前预算漂移影响最大的落点。
- 如果执行层仍能绕过统一 target，其他 artifact 再统一也没有意义。

备选但不采用：

- 仅修复 `portfolio_daily.csv` / `audit.json` 字段，不改下单。
  - 否决原因：那只是把审计改成“看起来一致”，真实执行仍错。

### 决策 4：审计必须把“target drift”作为合同问题显式暴露

选择：

- `research_audit` 对 formal ETF Phase 1 必须验证：orders、daily、rebalance summary 是否共享同一份 target exposure。
- 如果发现同一决策日 target 口径分叉，审计 MUST 输出明确的 contract drift 结论，而不是继续产出表面正常的 `avg_target_exposure`。

原因：

- 这类问题本质上是合同失真，不是普通策略表现波动。
- 项目优先级是可信、可审计、可解释，必须优先暴露这种口径冲突。

备选但不采用：

- 仅在开发态或单元测试中检查，不进入审计。
  - 否决原因：实验产物仍可能被误读为正式结论。

## Risks / Trade-offs

- [风险] 统一到 notional exposure 后，formal ETF 的交易规模和历史回测结果可能显著变化。  
  缓解：本 change 先定义合同，不预设收益方向；实现阶段必须重跑 formal study 并给出新旧对照。

- [风险] 当前 `requested_budget` / `applied_budget` 字段名可能已被下游脚本依赖。  
  缓解：优先保留字段名但统一语义；若必须新增说明性字段，应显式提供迁移说明。

- [风险] 即使 target 合同统一，`actual_exposure` 仍可能因月频 rebalance 与快照时点高于 target。  
  缓解：在 spec 中明确这是后续独立问题，避免把剩余偏差误判成合同未修复。

- [风险] 上游 Governor denominator 仍未解耦，统一后的 target 可能仍偏保守。  
  缓解：把 denominator 问题明确留在后续单独 L3 change，不与本 change 绑在一起。

## Migration Plan

1. 先在 OpenSpec 中为 ETF sleeve 与 research audit 补充单一目标仓位合同要求。
2. 实现阶段收敛 provider、contract、order sizing 和 daily accounting 的 target 语义，并为解释性 multiplier 改名或降级为 reason/evidence。
3. 增加单测与审计回归，锁定“同一决策日 orders / daily / audit 目标一致”。
4. 重跑 formal ETF study，对照 `orders.csv`、`portfolio_daily.csv`、`rebalance_day_summary.csv` 与 `audit.json` 的 ETF target 字段。
5. 若回归不可接受，回退 ETF target contract 相关文件，不触碰 Governor 主逻辑与 ETF 资产池。

## Open Questions

- 对外 artifact 是否继续保留 `requested_budget` / `applied_budget` 字段名，但将其语义统一为 notional exposure；还是新增 `approved_target_exposure` 并逐步迁移旧字段。
- `research_audit` 对 target drift 应输出 `FAIL` 还是 `WARN`，以及最小证据集合应包含哪些 artifact。
