## ADDED Requirements

### Requirement: audit.json 必须承接主线会计完整性摘要
系统 MUST 在现有 `audit.json` execution audit 结构中承接主线 `accounting_integrity` 审计摘要，使其与 `stage_pipeline`、`warnings` 和既有 execution audit 字段共存。

#### Scenario: execution audit 与 accounting_integrity 共存
- **WHEN** 一次实验通过标准 stabilize 流程写入 `audit.json`
- **THEN** `audit.json` SHALL 同时保留现有 `stage_pipeline`、`warnings` 和 `days_with_fills` 等字段
- **THEN** `audit.json` SHALL 额外包含 `accounting_integrity` 子树或等价 execution audit 摘要字段

#### Scenario: 证据不足时保留审计结果
- **WHEN** 当前正式执行路径未提供足够的会计快照证据
- **THEN** `audit.json` SHALL 仍然正常写盘
- **THEN** `accounting_integrity` SHALL 以 `UNKNOWN` 或等价状态表达证据不足，而不是缺失整份审计文件

### Requirement: 主审计文件中的会计样本输出必须受控
系统 MUST 在主审计文件中只保留有限会计失败样本与摘要计数，SHALL NOT 在 `audit.json` 中内联全量日级快照或全量持仓镜像。

#### Scenario: bounded sample 输出
- **WHEN** 某次实验存在多日会计失败样本
- **THEN** `audit.json` SHALL 仅保留受控数量的代表性样本
- **THEN** 审计摘要 SHALL 继续暴露总失败计数，避免样本截断改变总体判断
