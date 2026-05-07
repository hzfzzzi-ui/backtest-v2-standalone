## MODIFIED Requirements

### Requirement: 现金守恒检查
系统 SHALL 在每个交易日的 fill 执行后验证正式现金守恒等式；当显式 ETF 分红事件生效时，现金守恒必须把分红现金入账纳入同一条等式。

#### Scenario: 无成交无分红日
- **WHEN** 某交易日既没有 pending 订单需要执行，也没有 dividend cash credit
- **THEN** `cash_after` SHALL 等于 `cash_before`
- **THEN** `cash_check` SHALL 为 `true`

#### Scenario: 有成交无分红日
- **WHEN** 某交易日执行了买卖成交，但没有 dividend cash credit
- **THEN** `cash_after` SHALL 等于 `cash_before + Σ(sell_net) - Σ(buy_net)`
- **THEN** `cash_check` SHALL 为 `true`

#### Scenario: 有显式分红现金入账日
- **WHEN** 某交易日存在 ETF dividend cash credit
- **THEN** `cash_after` SHALL 等于 `cash_before + Σ(sell_net) + Σ(dividend_cash_credit) - Σ(buy_net)`
- **THEN** `cash_check` SHALL 为 `true`

## MODIFIED Requirements

### Requirement: NAV 一致性检查
系统 SHALL 在每个交易日的 NAV 快照后验证正式 NAV 等式；当 `pay_date` 口径下存在分红应收时，NAV 必须显式纳入 `dividend_receivable`。

#### Scenario: 无分红应收时 NAV 等式
- **WHEN** 某交易日不存在 `dividend_receivable`
- **THEN** `nav` SHALL 等于 `cash + market_value`（容差 0.01 元）
- **THEN** `nav_check` SHALL 为 `true`

#### Scenario: 存在分红应收时 NAV 等式
- **WHEN** 某交易日存在 `dividend_receivable`
- **THEN** `nav` SHALL 等于 `cash + dividend_receivable + market_value`（容差 0.01 元）
- **THEN** `nav_check` SHALL 为 `true`

#### Scenario: NAV 非 NaN
- **WHEN** 某交易日计算 NAV 快照
- **THEN** `nav` SHALL 不为 NaN 且不为负数
