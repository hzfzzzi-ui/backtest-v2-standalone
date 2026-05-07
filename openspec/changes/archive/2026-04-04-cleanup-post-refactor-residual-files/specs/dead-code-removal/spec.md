## MODIFIED Requirements

### Requirement: 死代码移除 MUST 以正式替代完成为前提
系统 MUST 仅在正式替代路径已经实现并验证通过后，才删除旧代码。死代码移除 SHALL NOT 被用作提前清理仍承担迁移职责的过渡层。

#### Scenario: 旧 bridge 仍承担结果中继
- **WHEN** 某个旧 bridge 仍承担迁移期结果中继职责
- **THEN** 系统 SHALL NOT 因其“看起来旧”而提前删除
- **THEN** 只有正式结果宿主落地后才允许将其纳入删除批次
