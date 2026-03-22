# Design

## Scope

本设计只给 `ma200_legacy` 增加一个最小 overlay。

明确不改：

- legacy 原始 `market_state` 计算
- legacy 原始 `trade_mode` 语义
- 个股信号
- 退出规则
- 周度五状态机原始打分逻辑

## Overlay Behavior

### Base behavior

基线仍由 `ma200_legacy` 决定：

- `market_state`
- `trade_mode`
- 预算乘子

### Overlay source

系统额外计算一条辅助 `weekly_five_state` 序列，仅用于识别：

- `TURN_WEAK`

该辅助序列不替换 legacy 原状态输出，只作为 veto overlay。

### Overlay rule

当以下条件同时满足时：

- `regime_engine.engine = ma200_legacy`
- `legacy_turn_weak_overlay.enabled = true`
- 辅助 weekly 状态为 `TURN_WEAK`

执行层 SHALL：

- 输出 `trade_mode = NO_TRADE`
- 输出 `risk_budget_multiplier = 0.0`

其余状态保持 legacy 原行为不变。

## Surface

最小配置面建议为：

- `regime_engine.legacy_turn_weak_overlay.enabled`
- `regime_engine.legacy_turn_weak_overlay.weekly_cfg`

其中 `weekly_cfg` 复用现有 `WeeklyFiveStateRegimeConfig`，避免再造一套参数。

## AB Design

最小 A/B：

1. `V10.2_LEGACY`
2. `V10.2_LEGACY_TURN_WEAK_ZERO`

共同约束：

- `2012-01-04 ~ 2026-03-16`
- `v2_canonical`
- `PIT_DYNAMIC`
- 同一个 `baseline_V10.2` 壳

## Rollback

回退路径：

- 删除 legacy overlay 配置字段
- 删除 overlay 接线
- 删除最小 A/B 脚本与产物
