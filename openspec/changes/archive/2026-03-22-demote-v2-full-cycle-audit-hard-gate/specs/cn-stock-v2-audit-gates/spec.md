## MODIFIED Requirements

### Requirement: `v2` 升格 MUST 通过 formal audit hard gate
系统 MUST 将 `V2 formal audit` 区分为 hard gate windows 与 advisory windows。hard gate windows 必须为：

- `2016-2026`
- `2012-2017`

系统 MAY 继续运行 `2007-2026` 作为全周期参考审计，但 SHALL NOT 将其作为 `V2` 升格的硬门槛。

#### Scenario: hard gate formal audit 未补齐时标记 incomplete
- **WHEN** `2016-2026` 或 `2012-2017` 任一窗口缺少正式 audit 产物
- **THEN** 系统 MUST 将 hard gate formal audit 状态标记为 incomplete
- **THEN** 系统 SHALL NOT 把 formal audit hard gate 视为已补齐

#### Scenario: advisory 全周期审计不阻断 hard gate
- **WHEN** `2007-2026` 审计产物尚未生成，或仍存在待治理的全周期异常
- **THEN** 系统 MAY 将其继续作为 advisory audit 保留
- **THEN** 系统 SHALL NOT 仅因 `2007-2026` 未通过而阻断 hard gate 判定

#### Scenario: formal audit 汇总显式区分 hard gate 与 advisory
- **WHEN** 系统执行 `V2 formal audit`
- **THEN** 汇总 MUST 输出 `required_windows`
- **THEN** 汇总 MUST 输出 `advisory_windows`
- **THEN** `required_windows` SHALL ONLY 包含 `2016-2026` 与 `2012-2017`
