## MODIFIED Requirements

### Requirement: `v2` 升格 MUST 通过三窗口 formal audit
系统 MUST 维护 `V2` formal audit 的固定三窗口，并仅在三窗口结果可复核时，才允许把 `pams_ohlcv_daily_v2` 视为 formal-audit-complete。固定窗口必须为：

- `2016-2026`
- `2012-2017`
- `2007-2026`

系统 SHALL NOT 继续把 `2007-2017` 作为 `V2 formal audit` 的硬门槛窗口。

#### Scenario: 三窗口 formal audit 未补齐时标记 incomplete
- **WHEN** `2016-2026`、`2012-2017`、`2007-2026` 任一窗口缺少正式 audit 产物
- **THEN** 系统 MUST 将 formal audit 状态标记为 incomplete
- **THEN** 系统 SHALL NOT 把 formal audit 视为已补齐

#### Scenario: 三窗口 formal audit 全部产出时标记 complete
- **WHEN** 系统已产出 `2016-2026`、`2012-2017`、`2007-2026` 三个窗口的正式 audit summary
- **THEN** 系统 MUST 生成一份统一 formal audit 汇总
- **THEN** 汇总 MUST 能指出每个窗口的 summary 路径和关键 gate 摘要

#### Scenario: 旧硬门槛窗口不再用于 V2 formal audit
- **WHEN** 用户执行 `V2 formal audit`
- **THEN** 系统 SHALL NOT 再把 `2007-2017` 作为固定执行窗口
