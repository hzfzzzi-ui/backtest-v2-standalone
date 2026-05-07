## ADDED Requirements

### Requirement: risk gate factor snapshots
系统 SHALL 输出独立的 risk gate factor snapshots 与 risk gate factor score snapshots。快照 MUST 包含 `raw_value`、`normalized_value`、`rank_value`、`availability_flag` 和 `asof_timestamp`，并 SHALL 明确 gate/veto/context 是否在当日可被正式研究消费。

#### Scenario: snapshot writes gate/veto availability
- **WHEN** 某个交易日缺少构成 risk gate 的必要上下文
- **THEN** snapshot MUST 将该因子该日标记为 `availability_flag=false`
- **THEN** 该日 SHALL NOT 参与正式 risk gate 因子统计
