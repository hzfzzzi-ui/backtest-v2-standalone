## ADDED Requirements

### Requirement: Governor 必须允许宽基 ETF sleeve 使用不同于个股 alpha 的本地暴露政策
`global_portfolio_governor` MUST 统一输出环境真相与总风险边界，但 MUST 允许宽基 ETF sleeve 在不绕过 Governor 的前提下使用不同于个股 alpha 的本地暴露翻译。

#### Scenario: 同一 Governor 支持不同 sleeve 响应函数
- **WHEN** 个股 alpha sleeve 与宽基 ETF sleeve 同时消费同一天的 Governor 输出
- **THEN** 系统 MUST 允许两者基于相同的 `effective_state_5` 得到不同的本地目标暴露
- **THEN** Governor SHALL NOT 要求所有 sleeve 共用同一套暴露响应函数

#### Scenario: Governor 仍保持统一总风险边界
- **WHEN** 宽基 ETF sleeve 使用更连续或更缓的暴露翻译
- **THEN** Governor MUST 继续对最终总风险预算与上限负责
- **THEN** 系统 SHALL NOT 因袖珍本地政策而绕开总风险约束
