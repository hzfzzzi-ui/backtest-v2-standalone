## ADDED Requirements

### Requirement: Breakout Failure / Exit Fragility Snapshots
系统 MUST 生成 `RESEARCH_ONLY` 的 breakout failure / exit fragility snapshots 与 factor score snapshots，用于按日记录失败风险与脆弱性上下文。

#### Scenario: Snapshot writer emits failure and fragility values
- **WHEN** 研究层按窗口生成 breakout failure / exit fragility snapshots
- **THEN** 系统 MUST 按交易日输出 failure/fragility 因子的 raw/normalized/rank/availability
- **AND** 输出 MUST 记录 as-of 时间和 lineage 信息
- **AND** 快照 MUST 不改变正式 runtime 行为
