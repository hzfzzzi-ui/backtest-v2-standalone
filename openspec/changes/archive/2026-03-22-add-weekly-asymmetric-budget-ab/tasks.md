# Tasks

## 1. Spec

- [x] 1.1 补充 `risk-budget-sizing` delta spec，声明 `asymmetric_budget` 预算模式
- [x] 1.2 补充 `regime-router` delta spec，声明 `TURN_WEAK / DEFENSIVE` 在该模式下关闭交易

## 2. Implementation

- [x] 2.1 在 `weekly_five_state_engine` 新增 `asymmetric_budget` 模式
- [x] 2.2 保持五档原始状态输出不变，仅调整预算与 `trade_mode`
- [x] 2.3 补充对应单测

## 3. AB

- [x] 3.1 新增 `baseline_V10.2` 最小 A/B 脚本，对比 legacy / weekly budget5 / weekly asymmetric
- [x] 3.2 生成正式 summary / report / performance comparison

## 4. Verification

- [x] 4.1 运行相关单测
- [x] 4.2 跑完最小 A/B 并确认 intended diff 清晰
- [x] 4.3 更新任务状态并给出回退路径
