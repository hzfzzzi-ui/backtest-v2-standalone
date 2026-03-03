# volatility-sizing (delta)

MA200 市场过滤器对 risk_budget trend_multiplier 的改动。

## MODIFIED Requirements

### Requirement: ATR 反比调仓
系统 SHALL 支持基于 ATR 的波动率反比仓位调整：波动率越高，仓位越小。

当 MarketFilterConfig.enabled == True 时，risk_budget 的 `trend_multiplier` SHALL 由 trade_mode 动态决定，替代静态配置值：
- trade_mode == TREND_MAIN → `trend_multiplier = MarketFilterConfig.bull_multiplier`（默认 1.5）
- trade_mode == TREND_LIGHT → `trend_multiplier = MarketFilterConfig.light_multiplier`（默认 0.6）
- trade_mode == NO_TRADE → `trend_multiplier = 0`（risk_amount = 0，买入被拦截）

当 MarketFilterConfig.enabled == False 时，`trend_multiplier` SHALL 使用 RiskBudgetConfig 中的静态值（默认 1.0），行为不变。

#### Scenario: BULL 态放大仓位
- **WHEN** market_filter 启用且 trade_mode == TREND_MAIN
- **THEN** portfolio_risk 计算中 trend_multiplier SHALL 为 bull_multiplier（默认 1.5）
- **THEN** 单笔 risk_amount = nav × portfolio_risk × dd_scale × trend_multiplier / max_positions

#### Scenario: TREND_LIGHT 态缩小仓位
- **WHEN** market_filter 启用且 trade_mode == TREND_LIGHT
- **THEN** trend_multiplier SHALL 为 light_multiplier（默认 0.6）

#### Scenario: NO_TRADE 态零仓位
- **WHEN** market_filter 启用且 trade_mode == NO_TRADE
- **THEN** trend_multiplier SHALL 为 0，risk_amount SHALL 为 0

#### Scenario: MA200 关闭时使用静态 multiplier
- **WHEN** market_filter 未启用
- **THEN** trend_multiplier SHALL 使用 RiskBudgetConfig.trend_multiplier 静态值
