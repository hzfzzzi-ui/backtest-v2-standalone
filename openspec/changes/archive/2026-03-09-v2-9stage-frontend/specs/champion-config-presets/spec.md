# Champion Config Presets

## ADDED Requirements

### Requirement: 预置 Breakout 冠军配置
系统 SHALL 预置一个 Breakout Trend 冠军配置文件，对应 3.4 号参数扫描优化结果（P3-D），可在前端"加载"下拉中直接调用。

配置核心参数：
- `strategy_pack: "BREAKOUT_TREND"`
- `signal_generation.strategy: "BREAKOUT_TREND"`
- `signal_generation.breakout.breakout_window: 20`
- `stock_trend_filter.enabled: false`
- `exit_rules.atr_stop: { enabled: true, k: 1.5 }`
- `exit_rules.trailing: { enabled: true, k: 3.0 }`
- `exit_rules.take_profit: { enabled: true, mode: "pct", pct: 0.20 }`
- `exit_rules.low10_exit: { enabled: true }`
- `exit_rules.hold_constraint: { min_hold_days: 5, cooldown_days: 5 }`
- `position_risk.max_positions: 10`
- `position_risk.risk_budget: { enabled: true, dd_reduce_pct: 0.10, dd_reduce_scale: 0.5 }`
- `universe_mode: "CSI800"`
- `universe.start: "2016-03-01"`, `universe.end: "2026-02-01"`
- `universe.benchmark: "000906.SH"`

#### Scenario: Breakout 冠军配置可在加载下拉中找到
- **WHEN** 用户点击前端"加载"按钮，调用 `GET /api/backtest_v2/configs`
- **THEN** 返回的配置列表中 SHALL 包含一条 name 含 "Breakout 冠军" 的配置项

#### Scenario: 加载 Breakout 冠军配置后 UI 正确回填
- **WHEN** 用户从加载下拉选择 Breakout 冠军配置
- **THEN** S6 策略选择器 SHALL 设为 BREAKOUT_TREND，breakout_window 设为 20，S9 退出面板中 ATR 止损 k=1.5、追踪 k=3.0、止盈 20% 均已勾选并填入正确值

#### Scenario: Breakout 冠军配置运行结果验证
- **WHEN** 用户从前端加载 Breakout 冠军配置并发起回测运行
- **THEN** 回测结果 SHALL 与 3.4 号脚本结果一致：CAGR 约 +5.46%，MDD 约 -24.32%

### Requirement: 预置 EMA Cross 冠军配置
系统 SHALL 预置一个 EMA Cross 冠军配置文件，对应 EMA(8,25) + TP30% + trail6 + min5cool5 组合，可在前端"加载"下拉中直接调用。

配置核心参数：
- `strategy_pack: "EMA_CROSS"`
- `signal_generation.strategy: "EMA_CROSS"`
- `signal_generation.ema.fast_ma: 8`, `slow_ma: 25`
- `exit_rules.atr_stop: { enabled: true, k: 2.0 }`
- `exit_rules.trailing: { enabled: true, k: 6.0 }`
- `exit_rules.take_profit: { enabled: true, mode: "pct", pct: 0.30 }`
- `exit_rules.hold_constraint: { min_hold_days: 5, cooldown_days: 5 }`
- `position_risk.max_positions: 10`
- `universe_mode: "CSI800"`
- `universe.start: "2016-03-01"`, `universe.end: "2026-02-01"`
- `universe.benchmark: "000906.SH"`

#### Scenario: EMA 冠军配置可在加载下拉中找到
- **WHEN** 用户点击前端"加载"按钮，调用 `GET /api/backtest_v2/configs`
- **THEN** 返回的配置列表中 SHALL 包含一条 name 含 "EMA 冠军" 的配置项

#### Scenario: 加载 EMA 冠军配置后 UI 正确回填
- **WHEN** 用户从加载下拉选择 EMA 冠军配置
- **THEN** S6 策略选择器 SHALL 设为 EMA_CROSS，fast_ma=8, slow_ma=25，S9 退出面板中 TP=30%, trail k=6.0 均正确回填

### Requirement: 冠军配置通过 _config_store 内置机制注册
冠军配置 SHALL 通过 `_config_store.py` 的内置配置机制注册（类似 `_ensure_builtin_flow_script_config()`），确保服务启动时自动创建。配置文件存储在 `outputs/configs/` 目录。

#### Scenario: 服务启动自动注册冠军配置
- **WHEN** 后端服务启动并首次调用配置列表 API
- **THEN** 系统 SHALL 自动在 `outputs/configs/` 目录创建冠军配置文件（如不存在）

#### Scenario: 配置未变更时不重复写入
- **WHEN** 冠军配置文件已存在且内容未变更
- **THEN** `_ensure_builtin_*` 函数 SHALL 跳过写入，不产生 I/O 开销
