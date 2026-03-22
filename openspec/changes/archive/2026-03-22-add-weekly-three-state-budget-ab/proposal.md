# Proposal

## Why

`weekly_five_state` 当前的五档风险预算映射与五档原始状态完全绑定，但前面的市场判断审计已经显示：

- 五档版在未来 20/60/120 日收益排序上明显不稳
- 压成三档后，`RISK_ON > RISK_OFF/NEUTRAL` 的短中期方向感更清楚
- 问题更像是执行层把状态切得过细，而不是原始五档打分本身必须全部废弃

在这种情况下，最小而可归因的下一步不是重写状态机，而是：

- 保持 `weekly_five_state` 的五档原始状态与原始分数不变
- 只把执行层风险预算映射压成三档
- 基于 `baseline_V10.2` 做一轮最小 A/B

## What Changes

本 change 只做三件事：

1. 为 `weekly_five_state` 新增“三档风险预算映射”执行模式
2. 保持五档原始状态输出、图表蒙版和审计字段不变
3. 基于 `baseline_V10.2` 运行最小 A/B，对比：
   - `ma200_legacy`
   - `weekly_five_state` 五档预算映射
   - `weekly_five_state` 三档预算映射

三档映射固定为：

- `BULL_MAIN + TURN_STRONG -> RISK_ON -> 100%`
- `LIGHT_TREND -> NEUTRAL -> 40%`
- `TURN_WEAK + DEFENSIVE -> RISK_OFF -> 0%`

## Impact

- 影响模块：
  - `weekly_five_state_engine`
  - runtime/day controls 对风险预算的消费链
  - `baseline_V10.2` 的研究 A/B 脚本
- 不影响：
  - 个股信号逻辑
  - breakout / residual 排序
  - 原始五档状态定义
  - `ma200_legacy` 默认主线

## Risks

- 可能出现“预算简化后交易数回升，但质量没有回升”
- 可能出现“预算压成三档后，状态判断更像样，但策略收益仍然差”
- 如果把 `TURN_WEAK` 直接归零，可能会过度压缩过渡带试探仓位

## Success Criteria

- A/B 输出可直接回答：
  - 三档预算映射是否明显优于五档预算映射
  - 三档预算映射是否仍明显落后 `ma200_legacy`
  - 交易数、回撤、收益是否出现可解释变化
