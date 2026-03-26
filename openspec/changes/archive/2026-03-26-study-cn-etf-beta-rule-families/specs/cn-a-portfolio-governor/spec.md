## ADDED Requirements

### Requirement: ETF 规则族研究必须显式声明 fallback 与 Governor 的边界
当 ETF 规则族研究包含防守 fallback 时，系统 MUST 明确该 fallback 是：
- ETF sleeve 内部资产切换
- 还是 Governor 级预算压缩后的结果

系统 SHALL NOT 允许 fallback 语义在 sleeve 内部和 Governor 外部同时隐式生效而无法区分。

#### Scenario: ETF 研究使用 `511010` 作为 fallback
- **WHEN** ETF 规则族实验切入 `511010`
- **THEN** 系统 MUST 能说明这是 ETF sleeve 内部 fallback，还是 Governor 下发的预算/防守偏置结果

### Requirement: ETF 规则族研究必须让 vol target 与预算语义对齐
当 ETF 规则族研究包含 `Vol Target` 时，系统 MUST 把风险缩放结果映射为可审计的 budget 语义，而不是只作为 provider 内部黑箱数值。

最小可见语义至少 MUST 包含：
- 缩放前预算
- 缩放后预算
- 缩放驱动来源

#### Scenario: Vol target 收缩 ETF sleeve 风险
- **WHEN** 近期波动超过规则阈值并触发 ETF sleeve 风险缩放
- **THEN** Governor 相关产物 MUST 能说明 ETF sleeve 预算如何变化
- **THEN** 该变化 MUST 能被归因到 volatility target，而不是被误解为 regime 或 drawdown 单独驱动
