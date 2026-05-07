## ADDED Requirements

### Requirement: 研究输出必须包含 snapshot lineage
系统 SHALL 在 snapshot-backed 研究输出中记录最小 lineage 信息，至少包括 snapshot 路径、window、variant、config hash 与 source trace。

#### Scenario: 研究结果可回溯到 snapshot 输入
- **WHEN** 任一 snapshot-backed 研究完成
- **THEN** 机器输出 SHALL 包含对应 snapshot 输入的 lineage 字段

#### Scenario: lineage 字段足以区分不同研究运行
- **WHEN** 两次研究消费不同 snapshot 或不同窗口
- **THEN** 系统 SHALL 在输出 lineage 中表现出可区分的引用信息
