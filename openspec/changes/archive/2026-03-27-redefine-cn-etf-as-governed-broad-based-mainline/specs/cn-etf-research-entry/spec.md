## ADDED Requirements

### Requirement: ETF研究入口必须支持独立宽基主线角色
`cn-etf` 研究入口 MUST 支持“受统一 Governor 管控的独立宽基轮动主线”配置模式。该模式 MUST 显式声明策略角色、宽基资产池、Governor 边界消费方式和本地 enter/exit policy。

#### Scenario: 研究入口展开独立宽基主线配置
- **WHEN** 用户选择宽基 ETF 独立主线研究入口
- **THEN** 系统 MUST 生成显式标记为 governed broad-based standalone mainline 的研究配置
- **THEN** `run_meta` MUST 能追溯该模式所使用的 Governor 边界和本地 policy 配置

### Requirement: ETF研究入口必须拒绝行业ETF混入本轮主线
当前宽基 ETF 独立主线研究入口 MUST 只允许宽基 ETF 候选池。系统 SHALL NOT 允许用户通过该入口把行业 ETF、主题 ETF 或其他非宽基资产静默混入。

#### Scenario: 用户尝试通过独立宽基主线入口加入行业ETF
- **WHEN** 研究配置通过该入口加入非宽基 ETF
- **THEN** 系统 MUST 返回显式边界错误或告警
- **THEN** 系统 SHALL NOT 将其继续编译为当前主线的有效配置
