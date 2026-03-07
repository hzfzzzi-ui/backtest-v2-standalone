## ADDED Requirements

### Requirement: 服务端报告中文文案可读
服务端自动生成的 `report.html` MUST 使用 UTF-8 可读中文文案，禁止出现乱码标题、乱码表头与乱码枚举值。

#### Scenario: 报告标题可读
- **WHEN** 打开 `GET /api/backtest_v2/experiments/{exp_id}/report`
- **THEN** 报告标题与章节标题 SHALL 以可读中文展示（例如“回测分析报告”“收益分析”）

### Requirement: BREAKOUT 策略摘要正确映射
当策略为 `BREAKOUT_TREND` 时，报告策略摘要 MUST 展示突破策略参数，而非 MA 快慢线通用字段。

#### Scenario: BREAKOUT 摘要字段
- **WHEN** `signal_generation.strategy = BREAKOUT_TREND`
- **THEN** 报告 SHALL 展示 `breakout_window`、`entry_confirm_mode`、`entry_delay_mode`、`portfolio_mode`
- **THEN** 报告不得将 `fast_ma/slow_ma` 作为该策略的核心入场参数展示

### Requirement: 报告展示值与运行产物一致
服务端报告中的关键数值 MUST 与同一实验的产物文件一致。

#### Scenario: 关键指标一致性
- **WHEN** 比对 `report.html` 与同目录产物
- **THEN** CAGR/Sharpe/MDD SHALL 与 `perf.json` 一致
- **THEN** 区间与基准 SHALL 与最终运行配置一致
