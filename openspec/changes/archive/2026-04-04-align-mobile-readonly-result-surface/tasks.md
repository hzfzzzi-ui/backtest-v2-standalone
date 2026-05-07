## 1. 正式角色收口

- [x] 1.1 定义移动端只读结果表面的正式能力与边界。（DoD: 新 capability spec 固定只读角色；验证: `openspec validate align-mobile-readonly-result-surface` 通过；风险: 旧审批语义继续混入）
- [x] 1.2 固定与桌面端共享的术语、指标口径、颜色、状态与错误提示边界。（DoD: specs 明确共享语义；验证: 场景可测试；风险: 两端继续漂移）

## 2. 旧语义降级

- [x] 2.1 将 `mobile-signal-dashboard` 收口为只读摘要与快速查看结果。（DoD: delta spec 不再把 dashboard 当审批主终端；验证: 场景完整；风险: dashboard 职责仍过重）
- [x] 2.2 将 `mobile-daily-briefing` 对齐桌面结果摘要与事务摘要语义。（DoD: delta spec 明确摘要来源；验证: OpenSpec validate 通过；风险: briefing 继续背旧职责）
