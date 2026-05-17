## ADDED Requirements

### Requirement: ETF 分红现金事件必须纳入正式 baseline 口径
正式 stock+ETF baseline 使用 `cn_etf` 数据源时，系统 MUST 将显式 ETF 分红事件作为 NAV 与现金流 truth 的一部分；当 ETF 分红事件已进入数据包时，系统 SHALL NOT 回退到仅依赖复权因子隐含表达分红收益的旧 baseline 口径。

#### Scenario: baseline rerun 使用显式 ETF 分红事件
- **WHEN** baseline rerun 的 ETF 数据包包含 `pit_cn_etf_dividend_events` 中覆盖回测窗口的分红事件
- **THEN** ETF sleeve MUST 在除息日创建对应分红权益或现金入账记录
- **THEN** ETF sleeve MUST 在到账日完成应收结转或现金确认
- **THEN** `portfolio_cash_events.csv` MUST 记录被处理的分红现金事件

#### Scenario: 首个已知分歧事件可被解释
- **WHEN** 回测持有 `sh510300` 且处理 `2015-01-20` 的 ETF 分红事件
- **THEN** 系统 MUST 将 `held_qty * div_cash` 作为该事件的分红权益金额
- **THEN** 该事件造成的 NAV 差异 MUST 能通过价格除权、应收分红和后续到账现金闭环解释

### Requirement: ETF 分红口径迁移必须保留审计证据
接受 ETF 显式分红现金事件作为正式口径时，系统 MUST 保留足够的差异证据，说明新旧 baseline 漂移来自数据口径补齐，而不是策略逻辑改动。

#### Scenario: 迁移说明记录分红数据包差异
- **WHEN** 新 baseline 替代旧 baseline
- **THEN** 迁移记录 MUST 包含旧候选与新候选的 ETF 分红事件行数
- **THEN** 迁移记录 MUST 包含首个 NAV 分歧日、分歧标的和对应分红事件
- **THEN** 迁移记录 MUST 明确股票层 NAV 未发生漂移
