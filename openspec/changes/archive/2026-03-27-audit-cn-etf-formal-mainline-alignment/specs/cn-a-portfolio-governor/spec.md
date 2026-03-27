## ADDED Requirements

### Requirement: Governor 约束不得被误读为 ETF 正式主线背书
Governor 继续是 ETF 正式主线与 ETF 研究分支的唯一合法上游状态和预算来源，但系统 MUST 区分“受 Governor 约束”与“符合 ETF Phase 1 正式口径”是两件不同的事。

仅因为某条 ETF 运行路径消费了 Governor 状态和预算，并不足以将其标记为 `formal_mainline`。

#### Scenario: 研究分支仍受 Governor 约束
- **WHEN** 某条 ETF 研究分支运行在统一 Governor 之下
- **THEN** 系统 MUST 承认其受 Governor 约束
- **THEN** 系统 SHALL NOT 因此自动将其视为正式 ETF 主线

#### Scenario: 正式主线必须同时满足上游约束和正式范围
- **WHEN** 某条 ETF 路径被标记为 `formal_mainline`
- **THEN** 它 MUST 同时满足统一 Governor 约束和 ETF 正式文档范围
