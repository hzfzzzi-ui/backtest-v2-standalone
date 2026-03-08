# Breakout Entry UI

## ADDED Requirements

### Requirement: S6 策略选择器支持四种策略类型
S6 入场信号面板的策略选择器 `<select id="wbTrendStrategy">` SHALL 包含以下四个选项：
- `SMA_CROSS`（均线交叉 SMA）
- `EMA_CROSS`（均线交叉 EMA）— 默认选中
- `BREAKOUT_TREND`（突破趋势 Breakout）
- `RSI_REVERSAL`（RSI 均值回归）

#### Scenario: 用户选择 BREAKOUT_TREND 策略
- **WHEN** 用户在 S6 面板中将策略选择器切换为 `BREAKOUT_TREND`
- **THEN** 系统 SHALL 隐藏 SMA/EMA 参数面板（fast_ma, slow_ma, entry_buffer_pct），显示 Breakout 参数面板（breakout_window）

#### Scenario: 用户选择 RSI_REVERSAL 策略
- **WHEN** 用户在 S6 面板中将策略选择器切换为 `RSI_REVERSAL`
- **THEN** 系统 SHALL 隐藏 SMA/EMA 参数面板和 Breakout 面板，显示 RSI 参数面板（rsi_period, rsi_buy_threshold, rsi_sell_threshold, mr_hold_days, mr_stop_loss_pct）

#### Scenario: 用户选择 SMA_CROSS 或 EMA_CROSS
- **WHEN** 用户在 S6 面板中将策略选择器切换为 `SMA_CROSS` 或 `EMA_CROSS`
- **THEN** 系统 SHALL 显示 SMA/EMA 参数面板（fast_ma, slow_ma, entry_buffer_pct），隐藏 Breakout 和 RSI 面板

### Requirement: Breakout 参数面板
S6 面板 SHALL 包含一个 Breakout 参数面板 `wbBreakoutParams`，仅在策略选择为 `BREAKOUT_TREND` 时显示。

面板包含以下控件：
- `wbBreakoutWindow`：突破窗口期（input number），默认值 20，范围 5-60

#### Scenario: Breakout 参数面板默认隐藏
- **WHEN** 页面初始加载（默认策略为 EMA_CROSS）
- **THEN** Breakout 参数面板 SHALL 处于隐藏状态

#### Scenario: Breakout 参数面板值生效
- **WHEN** 用户选择 BREAKOUT_TREND 策略并设置 breakout_window=15
- **THEN** `buildConfigDraft()` 生成的 config JSON 中 SHALL 包含 `signal_generation.breakout.breakout_window = 15`

### Requirement: RSI 参数面板
S6 面板 SHALL 包含一个 RSI 参数面板 `wbMrParamsRSI`，仅在策略选择为 `RSI_REVERSAL` 时显示。

面板包含以下控件：
- `wbRsiPeriod`：RSI 周期（input number），默认值 6，范围 2-30
- `wbRsiBuyThreshold`：RSI 买入阈值（input number），默认值 20，范围 5-50
- `wbRsiSellThreshold`：RSI 卖出阈值（input number），默认值 80，范围 50-95
- `wbMrHoldDays`：持仓天数上限（input number），默认值 10，范围 1-60
- `wbMrStopLoss`：止损百分比（input number），默认值 5，范围 1-30（单位：%）

#### Scenario: RSI 参数面板默认隐藏
- **WHEN** 页面初始加载（默认策略为 EMA_CROSS）
- **THEN** RSI 参数面板 SHALL 处于隐藏状态

#### Scenario: RSI 参数回填 UI
- **WHEN** 加载一个 `signal_generation.strategy = "RSI_REVERSAL"` 的配置
- **THEN** `applyConfigToUI()` SHALL 将策略选择器设为 RSI_REVERSAL，显示 RSI 面板，并将 rsi_period/buy/sell/hold/stop 回填到对应控件

### Requirement: buildConfigDraft 支持新策略类型
`buildConfigDraft()` 函数 SHALL 根据当前策略选择器的值生成对应的配置 JSON：

- **BREAKOUT_TREND**：生成 `signal_generation.strategy = "BREAKOUT_TREND"` + `signal_generation.breakout = { breakout_window }` 块
- **RSI_REVERSAL**：生成 `signal_generation.strategy = "RSI_REVERSAL"` + `signal_generation.mr = { rsi_period, rsi_buy_threshold, rsi_sell_threshold, mr_hold_days, mr_stop_loss_pct }` 块
- **SMA_CROSS / EMA_CROSS**：保持现有行为不变

#### Scenario: Breakout 策略配置生成
- **WHEN** 策略选择器为 BREAKOUT_TREND，breakout_window=20
- **THEN** 生成的 config JSON SHALL 包含 `{ signal_generation: { strategy: "BREAKOUT_TREND", breakout: { breakout_window: 20 } } }`

#### Scenario: RSI 策略配置生成
- **WHEN** 策略选择器为 RSI_REVERSAL，rsi_period=6, rsi_buy=20, rsi_sell=80, hold=10, stop=5
- **THEN** 生成的 config JSON SHALL 包含 `{ signal_generation: { strategy: "RSI_REVERSAL", mr: { rsi_period: 6, rsi_buy_threshold: 20, rsi_sell_threshold: 80, mr_hold_days: 10, mr_stop_loss_pct: 0.05 } } }`

### Requirement: applyConfigToUI 支持新策略类型反向映射
`applyConfigToUI()` 函数 SHALL 根据 config JSON 中的 `signal_generation.strategy` 值回填 UI：

- **BREAKOUT_TREND**：选中策略选择器 → 显示 Breakout 面板 → 填写 breakout_window
- **RSI_REVERSAL**：选中策略选择器 → 显示 RSI 面板 → 填写所有 RSI 参数
- **SMA_CROSS / EMA_CROSS**：保持现有行为不变

#### Scenario: 加载 Breakout 配置
- **WHEN** `applyConfigToUI()` 接收到含 `signal_generation.strategy = "BREAKOUT_TREND"` 且 `signal_generation.breakout.breakout_window = 15` 的配置
- **THEN** 策略选择器 SHALL 设为 BREAKOUT_TREND，Breakout 面板显示，breakout_window 控件值设为 15

#### Scenario: 加载 RSI 配置
- **WHEN** `applyConfigToUI()` 接收到含 `signal_generation.strategy = "RSI_REVERSAL"` 的配置
- **THEN** 策略选择器 SHALL 设为 RSI_REVERSAL，RSI 面板显示，所有 RSI 参数从配置中回填
