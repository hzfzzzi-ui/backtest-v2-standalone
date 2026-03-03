## MODIFIED Requirements

### Requirement: 固定止损优先级
- **WHEN** 退出优先级判断
- **THEN** 优先级 SHALL 为：RISK_OFF > ATR_STOP_LOSS > FIXED_STOP_LOSS > TREND_BREAK > TAKE_PROFIT > ATR_TRAIL > TIME_EXIT > CROSS_DOWN

#### Scenario: 固定止损优先于趋势破坏
- **WHEN** 同一天同一持仓同时满足固定止损条件和趋势破坏条件
- **THEN** reason_code SHALL 为 `FIXED_STOP_LOSS`（固定止损优先级高于趋势破坏）

#### Scenario: ATR止损优先于固定止损
- **WHEN** 同一天同一持仓同时满足 ATR 止损条件和固定百分比止损条件
- **THEN** reason_code SHALL 为 `ATR_STOP_LOSS`（ATR 止损优先级高于固定止损）
