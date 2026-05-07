## ADDED Requirements

### Requirement: Research high-quality ALL_A stock universe as an isolated stock-leg experiment
系统 MUST 支持将个股腿股票池作为单变量进行研究，比较当前 `HS300_ZZ500 + PIT_DYNAMIC` 基线与 `ALL_A + 高质量过滤` 实验组的窗口表现。

#### Scenario: Run stock-only A/B with only universe changed
- **WHEN** 研究任务聚焦于个股腿股票池
- **THEN** 实验 SHALL 保持 breakout、ranking、exit、预算和执行时点不变
- **AND** 仅改变 `universe_mode` 与相关过滤

### Requirement: Treat ALL_A as active-universe research, not PIT constituent research
系统 MUST 将 `ALL_A` 研究解释为基于 `pit_security_master + OHLCV availability` 的 as-of 活跃股票池，而 SHALL NOT 将其解释为 `PIT_DYNAMIC` 指数成分研究。

#### Scenario: Explain ALL_A lineage
- **WHEN** 研究使用 `ALL_A`
- **THEN** 结论 MUST 明确说明其不消费 `pit_index_constituents`
- **AND** 必须说明这与 `HS300_ZZ500 + PIT_DYNAMIC` 的口径差异
