# legacy-market-filter-ab Specification

## Purpose
TBD - created by archiving change add-legacy-market-filter-ab-sequence. Update Purpose after archive.
## Requirements
### Requirement: Legacy 市场过滤 A/B 序列实验

系统 SHALL 支持基于 `baseline_V10.2` 执行一个三步最小 A/B 序列实验，用于验证 legacy 过渡阶段执行是否过宽：

1. **AB1**：只拆分 `TRANS_UP / TRANS_DOWN` multiplier
2. **AB2**：在 AB1 基础上启用 `freeze_trans_up_entries`
3. **AB3**：在 AB2 基础上将 `long_ma_window` 从 `200` 调为 `160`

每一轮实验 MUST 从同一份 `baseline_V10.2` 基准配置克隆，并保证 intended diff 仅包含该轮新增变量。

系统 SHALL 支持基于 `baseline_V10.2` 执行一个三步最小 A/B 序列实验，用于验证 legacy 过渡阶段执行是否过宽：

1. **AB1**：只拆分 `TRANS_UP / TRANS_DOWN` multiplier
2. **AB2**：在 AB1 基础上启用 `freeze_trans_up_entries`
3. **AB3**：在 AB2 基础上将 `long_ma_window` 从 `200` 调为 `160`

每一轮实验 MUST 从同一份 `baseline_V10.2` 基准配置克隆，并保证 intended diff 仅包含该轮新增变量。

#### Scenario: AB1 intended diff
- **WHEN** 运行 AB1
- **THEN** 相对 baseline 的 intended diff SHALL 仅包含 `trans_down_multiplier` 与 `trans_up_multiplier`

#### Scenario: AB2 intended diff
- **WHEN** 运行 AB2
- **THEN** 相对 AB1 的 intended diff SHALL 仅包含 `freeze_trans_up_entries = true`

#### Scenario: AB3 intended diff
- **WHEN** 运行 AB3
- **THEN** 相对 AB2 的 intended diff SHALL 仅包含 `long_ma_window = 160`### Requirement: Legacy 市场过滤 A/B 产物

系统 SHALL 为该序列实验输出正式对照产物，至少包括：
- `summary.json`
- `report.md`
- `performance_comparison.csv`

产物 MUST 说明：
- baseline / AB1 / AB2 / AB3 的实验 ID
- 每组 intended diff
- 收益、年化、Sharpe、最大回撤、交易数
- 风险、验证与回退路径

#### Scenario: 正式对照产物完整
- **WHEN** 序列 A/B 运行完成
- **THEN** 输出目录 SHALL 同时包含 `summary.json`、`report.md`、`performance_comparison.csv`

### Requirement: Legacy 市场过滤 A/B 产物

系统 SHALL 为该序列实验输出正式对照产物，至少包括：
- `summary.json`
- `report.md`
- `performance_comparison.csv`

产物 MUST 说明：
- baseline / AB1 / AB2 / AB3 的实验 ID
- 每组 intended diff
- 收益、年化、Sharpe、最大回撤、交易数
- 风险、验证与回退路径

#### Scenario: 正式对照产物完整
- **WHEN** 序列 A/B 运行完成
- **THEN** 输出目录 SHALL 同时包含 `summary.json`、`report.md`、`performance_comparison.csv`

