## MODIFIED Requirements

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

### Requirement: 复合信号子表 — 条件渲染
当 `wc.signal_composition.enabled === true` 且 `wc.signal_composition.modules.length > 0` 时，须额外渲染一个「复合信号」子表。该子表 SHALL 标注"未实现"表明后端尚无复合信号逻辑。

#### Scenario: 复合信号启用且有模块
- **WHEN** wc.signal_composition.enabled = true, modules 非空
- **THEN** 渲染复合信号子表，标题后 SHALL 追加 `(未实现)` 标注

#### Scenario: 复合信号禁用或模块为空
- **WHEN** wc.signal_composition.enabled = false 或 modules 为空
- **THEN** 不渲染复合信号子表
