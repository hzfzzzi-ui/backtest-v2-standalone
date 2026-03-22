# Tasks

## 1. Spec

- [x] 1.1 补充 `risk-budget-sizing` delta spec，声明 `weekly_five_state` 支持 `three_state` 预算模式
- [x] 1.2 补充 `regime-router` delta spec，声明三档预算模式不改变五档原始状态与个股信号逻辑

## 2. Implementation

- [x] 2.1 在 `weekly_five_state_engine` 新增 `risk_budget_mode` 配置与三档预算映射
- [x] 2.2 保持原始五档状态输出不变，仅改变执行预算 multiplier
- [x] 2.3 补充对应单测

## 3. AB

- [x] 3.1 新增 `baseline_V10.2` 最小 A/B 脚本，对比 legacy / weekly budget5 / weekly budget3
- [x] 3.2 生成正式 summary / report / performance comparison

## 4. Verification

- [x] 4.1 运行相关单测
- [x] 4.2 跑完最小 A/B 并确认唯一 intended diff 清晰
- [x] 4.3 更新任务状态并给出回退路径
