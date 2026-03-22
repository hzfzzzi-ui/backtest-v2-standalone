## MODIFIED Requirements

### Requirement: MA200 四态市场分类

系统 SHALL 在 `RegimeRouterSignalProvider.precompute()` 和 legacy 运行时路径中，基于基准指数计算四种市场状态：
- **BULL**: benchmark close > MA(long_ma_window) 且长均线 slope >= 0
- **TRANS_DOWN**: benchmark close > MA(long_ma_window) 且长均线 slope < 0
- **TRANS_UP**: benchmark close < MA(long_ma_window) 且长均线 slope >= 0
- **BEAR**: benchmark close < MA(long_ma_window) 且长均线 slope < 0

长均线窗口 SHALL 由 `MarketFilterConfig.long_ma_window` 驱动，默认值为 `200`。

长均线 slope 定义为 `MA(long_ma_window)[t] - MA(long_ma_window)[t - slope_window]`，其中 `slope_window` 默认 20 个交易日。

市场状态 SHALL 存储为 `_market_state[T]` 数组（int8），在 precompute 阶段一次性计算。

#### Scenario: 默认仍使用 MA200
- **WHEN** `market_filter.long_ma_window` 未显式设置
- **THEN** 系统 SHALL 使用 `200` 作为长均线窗口

#### Scenario: 长均线窗口可配置
- **WHEN** `market_filter.long_ma_window = 160`
- **THEN** 系统 SHALL 使用 `MA160` 及其 slope 计算 `BULL / TRANS_DOWN / TRANS_UP / BEAR`

#### Scenario: 长均线数据不足
- **WHEN** 交易天数 < `long_ma_window + slope_window`，长均线或 slope 无法计算
- **THEN** 当日 `market_state` SHALL 默认为 `BULL`

### Requirement: MarketFilterConfig 配置

系统 SHALL 提供 `MarketFilterConfig` dataclass：
- `enabled: bool = False` — 总开关
- `long_ma_window: int = 200` — legacy 长均线窗口
- `slope_window: int = 20` — 长均线斜率计算回看窗口
- `bull_multiplier: float = 1.5` — BULL 态 risk_budget trend_multiplier
- `light_multiplier: float = 0.6` — TREND_LIGHT 默认 multiplier
- `trans_down_multiplier: float | None = None` — `TRANS_DOWN` 专用 multiplier；为 `None` 时回退到 `light_multiplier`
- `trans_up_multiplier: float | None = None` — `TRANS_UP` 专用 multiplier；为 `None` 时回退到 `light_multiplier`
- `freeze_trans_up_entries: bool = False` — 是否在 `TRANS_UP` 阶段禁止新开仓
- `ema_light_fast: int = 5` — 轻趋势 EMA 快线周期
- `ema_light_slow: int = 20` — 轻趋势 EMA 慢线周期

配置 SHALL 在 `BacktestConfig` 中作为 `market_filter: MarketFilterConfig` 字段存在。

#### Scenario: 过渡态 multiplier 分拆
- **WHEN** 用户显式设置 `trans_down_multiplier` 与 `trans_up_multiplier`
- **THEN** 系统 SHALL 在 `TRANS_DOWN` 与 `TRANS_UP` 使用各自 multiplier，而不是共享 `light_multiplier`

#### Scenario: 过渡态 multiplier 回退
- **WHEN** `trans_down_multiplier` 或 `trans_up_multiplier` 为 `None`
- **THEN** 对应状态 SHALL 回退使用 `light_multiplier`

#### Scenario: freeze_trans_up_entries 配置透传
- **WHEN** 用户在配置中设置 `freeze_trans_up_entries = true`
- **THEN** 参数 SHALL 经 API → loader → engine → signal_provider 完整透传
