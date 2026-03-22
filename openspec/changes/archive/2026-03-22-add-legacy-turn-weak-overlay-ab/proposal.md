# Proposal

## Why

前一轮 `weekly_five_state` 审计已经把一件事钉死了：

- `asymmetric` 相对 `budget5` 的净改善，全部来自 `TURN_WEAK -> 0`
- 这条有效修正并不依赖把整套 `weekly_five_state` 拿来替换 `ma200_legacy`

这说明下一步最值得验证的不是继续改 `weekly_five_state`，而是把这条单独有效的修正抽出来，叠加到更可信的 `ma200_legacy` 过滤器上，做最小 A/B。

## What Changes

本 change 只做三件事：

1. 为 `ma200_legacy` 新增一个可选 overlay：
   - 继续使用 legacy 原有 `market_state / trade_mode`
   - 额外计算 `weekly_five_state`
   - 当 overlay 状态为 `TURN_WEAK` 时，将执行层强制关闭为 `NO_TRADE / 0%`
2. 保持以下内容不变：
   - `40日突破 + 40日个股残差动量排序`
   - 原始 legacy 状态判定
   - 退出逻辑
   - 股票池 / 数据角色 / PIT 模式
3. 基于 `baseline_V10.2` 做最小 A/B：
   - `V10.2_LEGACY`
   - `V10.2_LEGACY_TURN_WEAK_ZERO`

## Intended Diff

唯一 intended diff 是：

- `ma200_legacy` 是否启用 `TURN_WEAK -> NO_TRADE` overlay

## Success Criteria

- 明确验证 `TURN_WEAK -> 0` 这条修正，在 legacy 主线下是否仍然有效
- 明确区分：
  - 这是 overlay 自身有效
  - 还是只在 `weekly_five_state` 全套状态机里才“看起来有效”
