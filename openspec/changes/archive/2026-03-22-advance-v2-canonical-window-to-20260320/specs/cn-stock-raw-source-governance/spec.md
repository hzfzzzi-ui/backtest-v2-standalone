## MODIFIED Requirements

### Requirement: `v2` 全历史回填 MUST 覆盖正式时间窗口
系统 MUST 支持 `2007-01-04` 到 `2026-03-20` 的全历史回填与重放，并将该窗口视为 `v2` 数据库补全的正式时间范围。系统 MUST 让 raw、canonical、moneyflow、AkShare fallback、full backfill 默认值与 runbook 正式命令共享同一 official window 终点定义。

#### Scenario: 全历史回填窗口固定
- **WHEN** 系统执行正式 `v2` 全量回填
- **THEN** 系统 MUST 覆盖 `2007-01-04` 到 `2026-03-20`

#### Scenario: 单日或分段回填与全量逻辑一致
- **WHEN** 系统执行单日、分段或补丁式回填
- **THEN** 系统 MUST 使用与全量回填相同的原始标准化和 canonical build 逻辑
- **THEN** 系统 SHALL NOT 为了快速补数据引入第二套写表逻辑

#### Scenario: 正式入口默认终点一致
- **WHEN** 用户运行正式 `v2` raw、main、moneyflow、audit 或 full backfill 入口且未显式指定截止日期
- **THEN** 系统 MUST 使用同一个 official window 终点
- **THEN** 系统 SHALL NOT 继续在不同入口保留彼此不一致的硬编码默认终点
