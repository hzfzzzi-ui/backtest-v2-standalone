# Design

## Scope

本设计只覆盖 `weekly_five_state` 的**执行层风险预算映射**。

明确不改：

- 五档 raw score 计算
- 五档 raw/smoothed state 定义
- 周度观察与升级/降级防抖
- 个股信号与主线 `40日突破 + 40日残差动量排序`

## Current Problem

当前 `weekly_five_state` 的预算映射是：

- `BULL_MAIN -> 1.00`
- `TURN_STRONG -> 0.70`
- `LIGHT_TREND -> 0.40`
- `TURN_WEAK -> 0.15`
- `DEFENSIVE -> 0.00`

这相当于把五档状态直接拿去驱动执行预算。

但前序审计表明：

- 五档状态在未来收益排序上不稳定
- 压成三档后方向排序更合理

因此这次只测试：

> 原始五档状态是否可以保留给审计与展示，而执行预算改走三档映射。

## Target Behavior

### Raw state stays five-state

系统仍然输出：

- `BULL_MAIN`
- `TURN_STRONG`
- `LIGHT_TREND`
- `TURN_WEAK`
- `DEFENSIVE`

并继续把：

- `market_state_raw_name`
- `market_state_smoothed_name`
- `market_state_score`
- `regime_confidence`
- `regime_transition_reason`

等字段原样下发。

### Execution budget collapses to three-state

新增一个执行层 bucket：

- `RISK_ON`
- `NEUTRAL`
- `RISK_OFF`

映射规则：

- `BULL_MAIN` / `TURN_STRONG` -> `RISK_ON`
- `LIGHT_TREND` -> `NEUTRAL`
- `TURN_WEAK` / `DEFENSIVE` -> `RISK_OFF`

预算规则：

- `RISK_ON = 1.00`
- `NEUTRAL = 0.40`
- `RISK_OFF = 0.00`

### Trade mode compatibility

为了最小改动，`trade_mode` 兼容保持：

- `RISK_ON` / `NEUTRAL` -> `TREND_MAIN`
- `RISK_OFF` -> `NO_TRADE`

这里不重新引入 `TREND_LIGHT`，避免把新旧状态语义重新绑死。

## Config Surface

在 `weekly_five_state` 配置下新增一个预算模式字段：

- `risk_budget_mode = "five_state" | "three_state"`

默认：

- `"five_state"`

这样可以保证：

- 现有实验结果不变
- 新实验只通过配置切换预算映射

## Minimal AB

最小 A/B 固定三条：

1. `V10.2_LEGACY`
2. `V10.2_WEEKLY_FIVE_STATE_BUDGET5`
3. `V10.2_WEEKLY_FIVE_STATE_BUDGET3`

共同约束：

- 同窗口：`2012-01-04 ~ 2026-03-16`
- 同数据：`v2_canonical + strict PIT`
- 同个股逻辑：`40日突破 + 40日残差动量排序`
- 同退出逻辑
- 唯一 intended diff：
  - `regime_engine.engine`
  - 或 `weekly_five_state.risk_budget_mode`

## Verification

需要验证三件事：

1. 单测：
   - 五档状态不变
   - 三档预算映射正确
   - `TURN_WEAK` 在 `three_state` 模式下不再给 `0.15`
2. A/B：
   - 生成正式三组对照结果
3. 审计：
   - 输出三组 performance comparison

## Rollback

回退非常简单：

- 删除 `three_state` 预算模式
- 保留 `five_state` 默认映射
- 删除本轮新增 A/B 脚本与产物
