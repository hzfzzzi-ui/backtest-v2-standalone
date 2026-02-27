## ADDED Requirements

### Requirement: 辅助函数 — 链式读取 workbench_config / base_config
`buildConfigSummary()` 须定义辅助函数 `wcVal(path, fallback)` 实现两层链式读取：先从 `overrides.workbench_config` 按 path 取值，取不到时 fallback 到 `base_config` 对应字段，仍取不到时返回 `"-"`。

#### Scenario: workbench_config 存在时优先读取
- **WHEN** config.json 包含 `overrides.workbench_config.signal_generation.sma.fast_ma = 5`
- **THEN** 报告信号策略表的「快线周期」显示 `5`

#### Scenario: workbench_config 缺失时 fallback 到 base_config
- **WHEN** config.json 不包含 `overrides.workbench_config`（API 直接调用场景）
- **THEN** 报告信号策略表的「快线周期」从 `base_config.strategy.fast` 读取并显示

#### Scenario: 两层均无数据时显示占位符
- **WHEN** `workbench_config` 和 `base_config` 均无对应字段
- **THEN** 该单元格显示 `"-"`

---

### Requirement: 子表 1 — 信号策略
报告 §6 须包含「信号策略」子表，以 `<h3>` + `<table>` 渲染，展示以下字段：
- 策略名称（wc.signal_generation.strategy / bc.strategy.name）
- 快线周期（wc.signal_generation.sma.fast_ma / bc.strategy.fast）
- 慢线周期（wc.signal_generation.sma.slow_ma / bc.strategy.slow）
- 入场缓冲（wc.signal_generation.sma.entry_buffer_pct）— 百分比显示
- ATR 窗口（bc.strategy.params.atr_n）
- ATR 倍数（wc.exit_rules.atr_stop.k / bc.strategy.params.atr_k）
- 趋势过滤 MA（bc.strategy.params.trend_ma）

#### Scenario: SMA_CROSS 策略参数完整
- **WHEN** config.json 中 wc.signal_generation.strategy = "SMA_CROSS"，sma.fast_ma = 5，sma.slow_ma = 20
- **THEN** 信号策略表显示策略名「SMA_CROSS」、快线「5」、慢线「20」

#### Scenario: 含 ATR 参数的策略
- **WHEN** base_config.strategy.params 包含 atr_n = 14, atr_k = 2.0, trend_ma = 60
- **THEN** 信号策略表额外显示「ATR 窗口 = 14」「ATR 倍数 = 2.0」「趋势过滤 MA = 60」

#### Scenario: params 字段不存在
- **WHEN** base_config.strategy 不含 params 字段
- **THEN** ATR 窗口、ATR 倍数、趋势过滤 MA 均显示 "-"

---

### Requirement: 子表 2 — 退出规则
报告 §6 须包含「退出规则」子表，展示以下字段：
- 反转退出（wc.exit_rules.signal_reverse）— 启用/禁用
- ATR 止损（wc.exit_rules.atr_stop.enabled + k）
- 追踪止损（wc.exit_rules.trailing.enabled + k）
- 时间退出（wc.exit_rules.time_exit.enabled + n_days）
- 退出优先级（wc.exit_priority）— 逗号分隔列表

#### Scenario: ATR 止损启用
- **WHEN** wc.exit_rules.atr_stop.enabled = true, k = 0.8
- **THEN** ATR 止损行显示「启用 (k=0.8)」

#### Scenario: 追踪止损禁用
- **WHEN** wc.exit_rules.trailing.enabled = false
- **THEN** 追踪止损行显示「禁用」

#### Scenario: 退出优先级列表
- **WHEN** wc.exit_priority = ["stop_loss", "reversal", "time", "trail"]
- **THEN** 退出优先级行显示「stop_loss → reversal → time → trail」

#### Scenario: 无 workbench_config 时退出规则全显示占位符
- **WHEN** config.json 不含 workbench_config
- **THEN** 退出规则子表所有字段显示 "-"

---

### Requirement: 子表 3 — 仓位与风控
报告 §6 须包含「仓位与风控」子表，展示以下字段：
- 最大持仓数（wc.position_risk.max_positions）
- 单票仓位上限（wc.position_risk.single_stock_cap）— 小数→百分比
- 行业仓位上限（wc.position_risk.industry_cap）— 小数→百分比
- 手数（wc.position_risk.lot / bc.execution.lot_size）
- 现金不足策略（wc.position_risk.cash_shortage_policy）
- 风险门（wc.risk_gate.enabled + drawdown_threshold + action + cooldown_days）

#### Scenario: 仓位上限百分比转换
- **WHEN** wc.position_risk.single_stock_cap = 0.1, industry_cap = 0.3
- **THEN** 单票仓位上限显示「10%」，行业仓位上限显示「30%」

#### Scenario: 风险门启用
- **WHEN** wc.risk_gate.enabled = true, drawdown_threshold = -0.1, action = "reduce", cooldown_days = 5
- **THEN** 风险门行显示「启用 — 回撤阈值 10%, 动作 reduce, 冷却 5 天」

#### Scenario: 风险门禁用
- **WHEN** wc.risk_gate.enabled = false
- **THEN** 风险门行显示「禁用」

---

### Requirement: 子表 4 — 选股范围
报告 §6 须包含「选股范围」子表，展示以下字段：
- 选股模式（wc.universe_mode 或 overrides.universe_mode）
- 标的数量（wc.universe.symbols.length 或 bc.universe.symbols.length）
- 排除 ST（wc.universe.filters.exclude_st）
- 排除停牌（wc.universe.filters.exclude_suspended）
- 最小上市天数（wc.universe.filters.min_list_days）
- 日均成交额下限（wc.universe.filters.min_avg_turnover_20d）— 格式化为万元
- 价格区间（wc.universe.filters.price_min ~ price_max）
- ATR 波动区间（wc.universe.filters.atr_pct_range）
- 涨跌停规则（wc.universe.filters.limit_rule）
- 价格口径（wc.universe.price_adj / overrides.price_adj）

#### Scenario: 完整过滤条件展示
- **WHEN** wc.universe.filters 包含 exclude_st=true, min_list_days=180, min_avg_turnover_20d=100000000
- **THEN** 排除 ST 显示「是」，最小上市天数显示「180」，日均成交额下限显示「10,000 万」

#### Scenario: 价格口径读取
- **WHEN** wc.universe.price_adj = "hfq"
- **THEN** 价格口径行显示「后复权 (hfq)」

#### Scenario: 选股模式 CUSTOM
- **WHEN** wc.universe_mode 不存在且 bc.universe.symbols 有 3 只标的
- **THEN** 选股模式显示 "-"，标的数量显示「3」

---

### Requirement: 子表 5 — 执行假设
报告 §6 须包含「执行假设」子表，展示以下字段：
- 佣金率（bc.costs.commission_rate）— 万分比显示（如 3‱）
- 最低佣金（bc.costs.commission_min）
- 印花税率（bc.costs.stamp_tax_rate）— 千分比显示（如 1‰）
- 滑点（bc.costs.slippage_bps）— 单位 bps
- 手数（bc.execution.lot_size）
- T+1（bc.execution.t_plus_one）— 是/否
- 初始资金（bc.initial_capital）— 货币格式

#### Scenario: 默认成本参数
- **WHEN** bc.costs = {commission_rate: 0.0003, commission_min: 5, stamp_tax_rate: 0.001, slippage_bps: 2}
- **THEN** 佣金率显示「3‱」，最低佣金显示「5.00」，印花税率显示「1‰」，滑点显示「2 bps」

#### Scenario: T+1 执行规则
- **WHEN** bc.execution.t_plus_one = true, lot_size = 100
- **THEN** T+1 显示「是」，手数显示「100」

---

### Requirement: 复合信号子表 — 条件渲染
当 `wc.signal_composition.enabled === true` 且 `wc.signal_composition.modules.length > 0` 时，须额外渲染一个「复合信号」子表，列出：
- 合成模式（wc.signal_composition.compose_mode）
- 每个模块的 name / role / weight / priority

#### Scenario: 复合信号启用且有模块
- **WHEN** wc.signal_composition.enabled = true, compose_mode = "WEIGHTED_SCORE", modules 包含 [{name: "momentum", role: "signal", weight: 0.6}, {name: "volume", role: "filter", weight: 0.4}]
- **THEN** 渲染复合信号子表，标题显示「复合信号 (WEIGHTED_SCORE)」，表格列出两行模块

#### Scenario: 复合信号启用但模块为空
- **WHEN** wc.signal_composition.enabled = true, modules = []
- **THEN** 不渲染复合信号子表

#### Scenario: 复合信号禁用
- **WHEN** wc.signal_composition.enabled = false
- **THEN** 不渲染复合信号子表

#### Scenario: 无 workbench_config
- **WHEN** config.json 不含 workbench_config
- **THEN** 不渲染复合信号子表
