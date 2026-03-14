# backtest-report-export Specification

## Purpose
TBD - created by syncing change polish-ui-and-export-report. Update Purpose after archive.

## Requirements

### Requirement: 导出回测报告按钮
工作台 SHALL 提供"导出报告"按钮，点击后在新浏览器标签页中打开后端已生成的 report.html。如果后端 report.html 不存在（旧实验），fallback 到前端本地生成。

#### Scenario: 回测完成后导出（后端报告存在）
- **WHEN** 用户点击"导出报告"按钮且当前实验有后端生成的 report.html
- **THEN** 系统 SHALL 在新标签页中打开 `/api/backtest_v2/experiments/{exp_id}/report`

#### Scenario: 后端报告不存在时 fallback
- **WHEN** 用户点击"导出报告"按钮但后端 report.html 不存在（404）
- **THEN** 系统 SHALL fallback 到前端 generateReport() 本地生成并在新标签页展示

#### Scenario: 无回测结果时导出
- **WHEN** 用户点击"导出报告"按钮但无已完成的回测结果
- **THEN** 系统 SHALL 提示"请先运行回测"

### Requirement: 报告包含概览章节
报告 §1 概览 SHALL 包含策略基本信息和核心 KPI。

#### Scenario: 概览内容
- **WHEN** 报告生成
- **THEN** §1 SHALL 显示：实验 ID、回测区间（起止日期）、基准指数代码
- **THEN** §1 SHALL 显示 KPI 卡片：年化收益（%）、最大回撤（%）、夏普比率、卡尔马比率、交易次数、换手率
- **THEN** §1 SHALL 显示策略评级（Tier）

### Requirement: 报告包含收益分析章节
报告 §2 收益分析 SHALL 包含月度和年度收益统计表格。

#### Scenario: 月度收益表
- **WHEN** 报告生成且 NAV 数据可用
- **THEN** §2 SHALL 包含月度收益表格，行为年份，列为 1-12 月 + 年度合计
- **THEN** 每格显示该月收益率（%），正值绿色、负值红色

#### Scenario: NAV 数据不可用
- **WHEN** 报告生成但 NAV 数据缺失
- **THEN** §2 SHALL 显示"NAV 数据不可用"

### Requirement: 报告包含风险分析章节
报告 §3 风险分析 SHALL 包含最大回撤明细。

#### Scenario: 回撤明细
- **WHEN** 报告生成且 NAV 数据可用
- **THEN** §3 SHALL 显示最大回撤幅度、回撤起始日期、回撤最低点日期
- **THEN** §3 SHALL 显示风险指标：夏普比率、卡尔马比率

### Requirement: 报告包含交易分析章节
报告 §4 交易分析 SHALL 包含交易统计和平仓原因分布。

#### Scenario: 交易统计
- **WHEN** 报告生成且交易数据可用
- **THEN** §4 SHALL 显示：总交易次数、买入次数、卖出次数
- **THEN** §4 SHALL 显示平仓原因分布表（reason_code 及对应次数，中文翻译）

#### Scenario: 信号漏斗
- **WHEN** 报告生成且漏斗数据可用
- **THEN** §4 SHALL 显示信号漏斗：原始信号 → 被拦截 → 下单 → 跳过 → 已平仓

### Requirement: 报告包含持仓分析章节
报告 §5 持仓分析 SHALL 包含持仓利用率和约束触发统计。未实现的约束 SHALL 标注"未实现"而非显示 0。

#### Scenario: 持仓统计
- **WHEN** 报告生成且 counters 数据可用
- **THEN** §5 SHALL 显示：平均持仓数、最大持仓数、空余仓位、仓位利用率（%）

#### Scenario: 未实现的约束统计
- **WHEN** 报告生成
- **THEN** 个股上限触发行 SHALL 显示 `未实现` 而非数值 0
- **THEN** 行业上限触发行 SHALL 显示 `未实现` 而非数值 0
- **THEN** 资金不足跳过和最小手数跳过 SHALL 正常显示计数值（这些已实现）

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

### Requirement: 子表 1 — 信号策略
报告 §6 须包含「信号策略」子表，以 `<h3>` + `<table>` 渲染，展示以下字段：
- 策略名称（wc.signal_generation.strategy / bc.strategy.name）
- 快线周期（wc.signal_generation.sma.fast_ma / bc.strategy.fast）
- 慢线周期（wc.signal_generation.sma.slow_ma / bc.strategy.slow）
- 入场缓冲（wc.signal_generation.sma.entry_buffer_pct）— 百分比显示
- 趋势过滤 MA（bc.strategy.params.trend_ma）

ATR 窗口和 ATR 倍数 SHALL NOT 出现在信号策略子表中（这些是退出参数，已在退出规则子表中展示）。

#### Scenario: SMA_CROSS 策略参数完整
- **WHEN** config.json 中 wc.signal_generation.strategy = "SMA_CROSS"，sma.fast_ma = 5，sma.slow_ma = 20
- **THEN** 信号策略表显示策略名「SMA_CROSS」、快线「5」、慢线「20」
- **THEN** 信号策略表 SHALL NOT 包含 ATR 窗口或 ATR 倍数行

#### Scenario: params 字段不存在
- **WHEN** base_config.strategy 不含 params 字段
- **THEN** 趋势过滤 MA 显示 "-"

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

### Requirement: 复合信号子表 — 条件渲染
当 `wc.signal_composition.enabled === true` 且 `wc.signal_composition.modules.length > 0` 时，须额外渲染一个「复合信号」子表。该子表 SHALL 标注"未实现"表明后端尚无复合信号逻辑。

#### Scenario: 复合信号启用且有模块
- **WHEN** wc.signal_composition.enabled = true, modules 非空
- **THEN** 渲染复合信号子表，标题后 SHALL 追加 `(未实现)` 标注

#### Scenario: 复合信号禁用或模块为空
- **WHEN** wc.signal_composition.enabled = false 或 modules 为空
- **THEN** 不渲染复合信号子表

### Requirement: 报告包含交易明细附录
报告 §7 附录 SHALL 包含全部交易记录明细表。

#### Scenario: 交易明细表
- **WHEN** 报告生成且交易数据可用
- **THEN** §7 SHALL 包含全部交易记录表格，列为：日期、标的、方向、价格、数量、金额、原因
- **THEN** 方向列 SHALL 显示中文（买入/卖出）
- **THEN** 金额列 SHALL 显示千分位格式

### Requirement: 数据格式专业化显示
工作台所有数值 SHALL 按语义类型使用对应格式函数显示。

#### Scenario: KPI 卡片格式化
- **WHEN** KPI 面板渲染
- **THEN** 年化收益、最大回撤、换手率、Top10集中度 SHALL 显示为百分比（如 -2.18%）
- **THEN** 夏普比率、卡尔马比率 SHALL 显示 2 位小数（如 -0.05）
- **THEN** 交易次数 SHALL 显示千分位整数（如 2,166）

#### Scenario: 交易明细表格式化
- **WHEN** 交易明细表渲染
- **THEN** 价格 SHALL 显示 3 位小数
- **THEN** 数量 SHALL 显示千分位整数
- **THEN** 金额 SHALL 显示千分位 + 2 位小数

#### Scenario: Explain 面板计数器格式化
- **WHEN** Explain 面板触发统计渲染
- **THEN** 计数类指标（exit count、block count）SHALL 显示为整数
- **THEN** 比率类指标（applied_rate、on_rate）SHALL 显示为百分比

### Requirement: 界面中文化
工作台 SHALL 将所有英文标签翻译为中文（保留技术缩写如 ATR、SMA）。

#### Scenario: KPI 标签中文化
- **WHEN** KPI 面板渲染
- **THEN** 标签 SHALL 为：年化收益、最大回撤、夏普比率、卡尔马比率、交易次数、换手率、Top10集中度、评级

#### Scenario: 图表图例中文化
- **WHEN** 回撤图渲染
- **THEN** 图例 SHALL 显示"策略回撤"和"基准回撤"

#### Scenario: Explain 面板中文化
- **WHEN** 触发统计表渲染
- **THEN** 表头 SHALL 为"计数器"和"值"
- **THEN** 计数器名称 SHALL 翻译为中文（如 atr_stop_exit_count → ATR止损平仓）

#### Scenario: Execution 面板中文化
- **WHEN** Execution 面板渲染
- **THEN** "Candidates TopN" SHALL 显示为"候选标的 TopN"
- **THEN** "Target positions" SHALL 显示为"目标持仓"

#### Scenario: 交易原因码中文化
- **WHEN** 交易明细或报告中显示 reason_code
- **THEN** 已知 reason_code SHALL 翻译为中文（SMA_CROSS_UP → 均线金叉）
- **THEN** 未知 reason_code SHALL 显示原始值作为 fallback

### Requirement: 交易明细表美化
交易明细表 SHALL 具备专业金融软件的视觉品质。

#### Scenario: 方向列样式
- **WHEN** 交易明细表渲染
- **THEN** 买入 SHALL 显示为绿色 badge 标签
- **THEN** 卖出 SHALL 显示为红色 badge 标签

#### Scenario: 数字列对齐
- **WHEN** 交易明细表渲染
- **THEN** 价格、数量、金额列 SHALL 右对齐并使用等宽字体

### Requirement: perf.json 包含完整 KPI 字段
perf.json SHALL 包含 calmar、top10_profit_concentration、tier 三个字段。

#### Scenario: Calmar 比率计算
- **WHEN** 回测完成且 max_drawdown ≠ 0
- **THEN** perf.json 的 `calmar` SHALL 等于 `cagr / |max_drawdown|`

#### Scenario: Calmar 比率边界值
- **WHEN** max_drawdown = 0（无回撤）
- **THEN** `calmar` SHALL 为 0.0

#### Scenario: Top10 利润集中度
- **WHEN** 回测完成且存在盈利交易
- **THEN** `top10_profit_concentration` SHALL 等于利润最高的 10 只股票利润之和 / 全部正利润之和
- **THEN** 值域 SHALL 为 [0, 1]

#### Scenario: Top10 无盈利
- **WHEN** 回测完成但无正利润
- **THEN** `top10_profit_concentration` SHALL 为 0.0

#### Scenario: 策略评级
- **WHEN** 回测完成
- **THEN** `tier` SHALL 基于 sharpe、max_drawdown、calmar 分级：
  - T1: sharpe >= 1.0 且 max_drawdown > -0.20 且 calmar >= 1.0
  - T2: sharpe >= 0.5 且 max_drawdown > -0.30
  - T3: sharpe >= 0.0
  - T4: 其他

### Requirement: 前端 KPI 面板显示完整
KPI 面板 SHALL 正确显示所有 8 个 KPI 字段的计算值。

#### Scenario: KPI 非空显示
- **WHEN** 回测完成且 perf.json 包含字段值
- **THEN** 卡尔马比率 SHALL 显示数值（非 0.00 除非实际为 0）
- **THEN** Top10集中度 SHALL 显示百分比（非 —）
- **THEN** 评级 SHALL 显示 T1/T2/T3/T4（非 —）

### Requirement: 报告导出必须使用 Markdown
工作台 SHALL 提供 Markdown 报告导出，不再打开或导出后端 `report.html`。

#### Scenario: 导出已有实验报告
- **WHEN** 用户点击导出报告
- **THEN** 系统 SHALL 导出当前实验的 Markdown 报告
- **THEN** 系统 SHALL NOT 打开 `report.html`

#### Scenario: 无实验结果时导出
- **WHEN** 用户点击导出报告但当前没有可用实验结果
- **THEN** 系统 SHALL 提示用户先运行或加载实验
