# Tasks

## 1. Spec

- [x] 1.1 补充 `regime-router` delta spec，声明 legacy 可选接入 `TURN_WEAK -> NO_TRADE` overlay
- [x] 1.2 补充 `risk-budget-sizing` delta spec，声明 overlay 命中时预算归零

## 2. Implementation

- [x] 2.1 新增 legacy overlay 配置字段
- [x] 2.2 在 runtime/provider 接入 weekly `TURN_WEAK` veto overlay
- [x] 2.3 保持 legacy 原状态输出不变，仅覆盖执行层 `trade_mode / risk_budget_multiplier`
- [x] 2.4 补充对应单测

## 3. AB

- [x] 3.1 新增 `baseline_V10.2` 最小 A/B 脚本，对比 legacy / legacy_turn_weak_zero
- [x] 3.2 生成正式 summary / report / performance comparison

## 4. Verification

- [x] 4.1 运行相关单测
- [x] 4.2 跑完最小 A/B 并确认唯一 intended diff 清晰
- [x] 4.3 更新任务状态并给出回退路径
