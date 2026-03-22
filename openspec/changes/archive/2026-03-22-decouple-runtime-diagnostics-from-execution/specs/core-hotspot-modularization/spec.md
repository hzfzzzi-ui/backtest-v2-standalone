## ADDED Requirements

### Requirement: Default runtime daily loop 不得继续承担最终 diagnostics 口径
系统 MUST 将 default runtime daily loop 收口为执行主循环与原始事件汇总 owner。`strict_runtime_daily_loop.py` SHALL NOT 继续直接定义最终 buy funnel、stage note 或 surface-facing diagnostics 口径。

#### Scenario: default runtime 日循环执行
- **WHEN** `strict_runtime_daily_loop.py` 完成某个交易日的执行处理
- **THEN** 它 MUST 只输出执行原始事件、debug plan 和 diagnostics input
- **THEN** 最终 diagnostics 归一化 MUST 由独立 diagnostics builder 完成

#### Scenario: 继续拆 daily loop 热点
- **WHEN** 后续继续拆分 default runtime daily loop
- **THEN** 系统 SHALL NOT 因结构调整改变 diagnostics 最终值
- **THEN** diagnostics contract MUST 成为保护执行本体不被诊断逻辑反向污染的边界
