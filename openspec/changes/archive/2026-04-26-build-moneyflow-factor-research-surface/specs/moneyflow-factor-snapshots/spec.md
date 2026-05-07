## ADDED Requirements

### Requirement: moneyflow factor snapshots
系统 SHALL 输出独立的 moneyflow factor snapshots 与 moneyflow factor score snapshots。快照 MUST 包含 `raw_value`、`normalized_value`、`rank_value`、`availability_flag` 和 `asof_timestamp`，并 SHALL 明确可用性是否通过 moneyflow coverage 约束。

#### Scenario: snapshot writes availability under coverage gate
- **WHEN** 某个观测日的 moneyflow 因子覆盖率不足
- **THEN** snapshot MUST 将该日标记为 `availability_flag=false`
- **THEN** 该日 SHALL NOT 参与正式因子统计
