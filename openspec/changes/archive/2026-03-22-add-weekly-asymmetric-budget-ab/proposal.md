# Proposal

## Why

前一轮 `weekly_five_state` 预算实验已经给出两个稳定结论：

- `TURN_WEAK -> NO_TRADE` 是有效的，能减少亏损
- `TURN_STRONG -> 100%` 是无效的，会放大亏损

这说明问题不在于必须把五档压成完全对称的三档，而在于执行预算应该采用一个**非对称映射**：

- 关闭真正弱态
- 保留强转段的试探仓位，而不是直接满仓

## What Changes

本 change 只做三件事：

1. 为 `weekly_five_state` 新增 `asymmetric_budget` 执行模式
2. 保持五档原始状态、原始分数、周度观察与防抖不变
3. 基于 `baseline_V10.2` 做最小 A/B，对比：
   - `ma200_legacy`
   - `weekly_five_state + five_state`
   - `weekly_five_state + asymmetric_budget`

## Asymmetric Mapping

- `BULL_MAIN -> 1.00`
- `TURN_STRONG -> 0.70`
- `LIGHT_TREND -> 0.40`
- `TURN_WEAK -> 0.00`
- `DEFENSIVE -> 0.00`

trade mode 兼容：

- `BULL_MAIN / TURN_STRONG / LIGHT_TREND -> TREND_MAIN`
- `TURN_WEAK / DEFENSIVE -> NO_TRADE`

## Impact

- 影响模块：
  - `weekly_five_state_engine`
  - `baseline_V10.2` 的研究 A/B 脚本
- 不影响：
  - 个股信号
  - 原始五档状态输出
  - `ma200_legacy` 默认主线

## Success Criteria

- 验证 `asymmetric_budget` 是否优于 `five_state`
- 验证它是否显著优于上一轮 `three_state`
- 回答这条非对称映射是否值得继续研究
