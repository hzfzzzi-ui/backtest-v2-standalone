## ADDED Requirements

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
