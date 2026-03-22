## ADDED Requirements

### Requirement: RegimeRouter 必须消费正式 regime engine 输出
当 `market-regime-framework` 启用时，`regime-router` SHALL 以正式 regime engine 的输出作为唯一状态输入，至少消费以下字段：
- `market_state`
- `regime_confidence`
- `regime_duration_bars`
- `regime_transition_reason`
- `feature_availability`

`regime-router` MUST 不再假设 `market_state` 仅由 `close vs MA200 + slope` 唯一决定。

#### Scenario: Router 使用正式状态输入
- **WHEN** 正式市场状态框架启用
- **THEN** RegimeRouter MUST 从正式 regime engine 读取状态与置信度，而不是自行重算简化均线状态

### Requirement: trade_mode 必须由状态、置信度和 persistence 联合生成
当正式市场状态框架启用时，`trade_mode` SHALL 由 `market_state`、`regime_confidence`、`regime_duration_bars` 与执行确认条件联合决定，而不是简单的一对一映射。系统 MUST 允许表达：
- `market_state = TRANS_UP` 但 `trade_mode = NO_TRADE`
- `market_state = TRANS_DOWN` 但 `trade_mode = TREND_LIGHT`

#### Scenario: 低置信度 TRANS_UP 不开启交易
- **WHEN** `market_state = TRANS_UP` 且 `regime_confidence` 低于配置阈值
- **THEN** trade_mode MUST 保持 `NO_TRADE`

#### Scenario: 高置信度过渡态允许轻仓交易
- **WHEN** `market_state` 为过渡态且满足 persistence 与执行确认条件
- **THEN** trade_mode MAY 进入 `TREND_LIGHT`

### Requirement: RegimeRouter 必须输出状态到信号与日度产物
当正式市场状态框架启用时，RegimeRouter 产生的信号和日度产物 MUST 带出正式状态语义，用于前端显示与审计。至少包括：
- `market_state`
- `trade_mode`
- `regime_confidence`
- `regime_engine`

#### Scenario: 信号 meta 携带正式状态
- **WHEN** RegimeRouter 产生任意 BUY/SELL 信号
- **THEN** Signal.meta MUST 包含当前正式状态字段与 `regime_engine`
