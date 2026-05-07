## MODIFIED Requirements

### Requirement: Governor MUST 以预算与 `risk_override_v1` 参与共享执行边界
系统 MUST 将 Governor 的跨共享执行边界正式输出收口为预算边界和 `risk_override_v1`。Governor SHALL NOT 通过旧 combo 独立模块或隐式壳直接接管执行层语义。

#### Scenario: Governor 触发 reduce-only
- **WHEN** Governor 判定组合进入 `REDUCE_ONLY`
- **THEN** 系统 MUST 通过 `risk_override_v1` 下发该约束
- **THEN** 普通 `BUY` MUST 被阻断，普通 `SELL` MAY 继续执行
