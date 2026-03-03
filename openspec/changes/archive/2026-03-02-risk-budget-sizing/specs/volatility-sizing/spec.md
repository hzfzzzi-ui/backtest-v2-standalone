## REMOVED Requirements

### Requirement: ATR 反比调仓
**REMOVED** — 被 `risk-budget-sizing` 完全替代。

原有的 `enable_volatility_sizing` 开关、`vol_target_risk_pct` 参数、ATR 反比公式（`risk_amount / (atr/close)`）以及 30%-200% 上下限逻辑全部移除。

新系统使用风险预算公式（`risk_amount / (k × ATR)`）替代，通过组合风险分配而非简单反比缩放来确定仓位。

### Requirement: 波动率调仓可观测性
**REMOVED** — `vol_sizing` 诊断对象不再生成。可观测性由 risk-budget-sizing 的 daily_row 字段和 counters 替代。

### Requirement: 前端波动率调仓配置
**REMOVED** — "波动率调仓" checkbox 及参数输入从前端移除。替代 UI 为 risk-budget-sizing 的"风险预算"控件组。
