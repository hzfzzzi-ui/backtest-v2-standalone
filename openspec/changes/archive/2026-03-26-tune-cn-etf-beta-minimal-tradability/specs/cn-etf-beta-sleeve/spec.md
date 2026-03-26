## ADDED Requirements

### Requirement: ETF beta sleeve 必须具备最小可交易规则
`cn-etf-beta-sleeve` MUST 提供独立于股票 breakout 壳的最小可交易规则。该规则 MUST 以低频 ETF beta 选标为核心，且 SHALL 只消费 ETF 真值表、Governor 预算与 canonical 五状态，不得依赖股票 PIT、个股 breakout 候选或股票局部 budget 控制语义。

#### Scenario: ETF beta sleeve 走独立 selector
- **WHEN** 系统以 `asset_scope=cn_etf` 运行 `cn_etf_beta` 主线
- **THEN** ETF 选标与调仓 MUST 走 ETF beta 的独立 selector/provider
- **THEN** 系统 SHALL NOT 继续复用股票 breakout 候选、资金流排序或个股 ATR breakout 壳

### Requirement: ETF beta sleeve 必须采用低频相对强弱与绝对过滤组合
Phase 1 中，`cn-etf-beta-sleeve` MUST 采用低频调仓、相对强弱排序与单一绝对趋势过滤的最小规则。系统 MUST 至少支持：

- 周频调仓
- 正式候选池仅限 `510300.SH / 510500.SH / 510050.SH / 512100.SH`
- 绝对过滤：`close > MA120`
- 相对强弱：至少消费 `120d_return` 与 `60d_return`

#### Scenario: 周频调仓与趋势过滤生效
- **WHEN** ETF beta sleeve 进入正式调仓日
- **THEN** 系统 MUST 先按绝对趋势过滤可交易 ETF
- **THEN** 系统 MUST 再按低频相对强弱对正式候选池排序

### Requirement: ETF beta sleeve 必须定义五状态下的持仓上限
`cn-etf-beta-sleeve` MUST 在 canonical 五状态下定义最小持仓上限，且该映射 SHALL 不通过三状态反推。Phase 1 至少满足：

- `BULL`: 最多 2 只 core beta ETF
- `TRANS_UP`: 最多 2 只 core beta ETF
- `LIGHT`: 最多 1 只 core beta ETF
- `TRANS_DOWN`: 0 只 core beta ETF
- `RISK_OFF`: 0 只 core beta ETF

#### Scenario: 五状态决定 ETF beta 持仓上限
- **WHEN** Governor 向 ETF beta sleeve 下发 `effective_state_5`
- **THEN** ETF beta sleeve MUST 根据该五状态决定最大 deployable 持仓数
- **THEN** 系统 SHALL NOT 仅依赖 coarse 3-state 或股票 `trade_mode` 重建该上限

### Requirement: ETF beta sleeve 的正式 smoke 必须证明最小可交易性
`cn-etf-beta-sleeve` 的正式 smoke SHALL 不再只验证路径通过。对 `etf/cn_etf_first_wave_core` 的 `1626` 主 smoke，系统 MUST 同时证明：

- provider/read path 真值正确
- ETF beta 解释链完整
- `orders > 0`
- `trades > 0`

#### Scenario: ETF beta smoke 通过最小可交易门槛
- **WHEN** 系统运行 `etf/cn_etf_first_wave_core` 的 `1626` smoke
- **THEN** `research_audit` MUST 能证明 ETF beta 路径、解释链和最小可交易性同时成立
- **THEN** 若 `orders = 0` 或 `trades = 0`，系统 SHALL NOT 把该 smoke 视为通过
