## ADDED Requirements

### Requirement: Final Score Composition Snapshots
系统 MUST 生成 `RESEARCH_ONLY` 的 final score composition snapshots 与 factor score snapshots，用于按日记录 `_final_score` 组成项和总分。

#### Scenario: Snapshot writer emits composition values
- **WHEN** 研究层按窗口生成 final score composition snapshots
- **THEN** 系统 MUST 按交易日输出组成项与 `_final_score` 的 raw/normalized/rank/availability
- **AND** 输出 MUST 记录 as-of 时间和 lineage 信息
- **AND** 快照 MUST 不改变正式 runtime 行为
