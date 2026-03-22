# Design

## Scope

本设计只修改 `weekly_five_state` 的执行预算映射。

明确不改：

- 五档原始状态打分
- `weekly_observation`
- 升级 2 周确认 / 降级 1 周确认
- 个股 breakout / residual 主线逻辑

## Problem Reframing

前面的结果表明：

- `TURN_WEAK` 在执行层上更像风险关闭状态
- `TURN_STRONG` 仍然像一个过渡上行状态，不适合直接升到 `100%`

因此执行层应采用**非对称预算**，而不是把五档生硬压成对称三档。

## Target Behavior

### Raw states stay unchanged

继续保留：

- `BULL_MAIN`
- `TURN_STRONG`
- `LIGHT_TREND`
- `TURN_WEAK`
- `DEFENSIVE`

原始输出字段不变：

- `market_state_raw_name`
- `market_state_smoothed_name`
- `market_state_score`
- `regime_confidence`
- `regime_transition_reason`

### New budget mode

新增：

- `risk_budget_mode = "asymmetric_budget"`

预算映射：

- `BULL_MAIN -> 1.00`
- `TURN_STRONG -> 0.70`
- `LIGHT_TREND -> 0.40`
- `TURN_WEAK -> 0.00`
- `DEFENSIVE -> 0.00`

trade mode：

- `BULL_MAIN / TURN_STRONG / LIGHT_TREND -> TREND_MAIN`
- `TURN_WEAK / DEFENSIVE -> NO_TRADE`

## AB Design

最小 A/B：

1. `V10.2_LEGACY`
2. `V10.2_WEEKLY_BUDGET5`
3. `V10.2_WEEKLY_ASYMMETRIC`

共同约束：

- `2012-01-04 ~ 2026-03-16`
- `v2_canonical`
- `PIT_DYNAMIC`
- 同个股信号与退出

唯一 intended diff：

- `regime_engine.engine`
- `weekly_five_state.risk_budget_mode`

## Rollback

回退路径：

- 删除 `asymmetric_budget` 模式
- 恢复 `five_state` 默认逻辑
- 删除本轮 A/B 脚本与产物
