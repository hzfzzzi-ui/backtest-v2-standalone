## ADDED Requirements

### Requirement: 共享运行时合同必须隔离 ETF 研究字段
系统 MUST 保证 ETF 子系统进入共享执行链的正式运行时合同与 ETF 研究字段隔离。`target_book_v1` 及其等价正式执行合同 SHALL 只包含统一目标持仓所需字段，而 SHALL NOT 继续携带 ETF 私有预算、节奏、缺口和恢复解释字段。

#### Scenario: ETF 进入 target_book_v1
- **WHEN** ETF 子系统生成 `target_book_v1`
- **THEN** 合同 MUST 只表达最终目标持仓、约束、优先级与正式原因码
- **THEN** 合同 SHALL NOT 内联 `requested_budget`、`applied_budget`、`deployment_pace`、`strategic_floor_cap`、`tactical_overlay_cap`、`limited_defense_cap` 或任意 gap 字段

#### Scenario: 共享执行层消费 ETF 正式合同
- **WHEN** 共享执行层消费 ETF 生成的正式运行时合同
- **THEN** 执行层 MUST 只依赖统一目标持仓语义完成下单与持仓更新
- **THEN** 执行层 SHALL NOT 因 ETF 子系统私有研究字段而形成新的隐式耦合
