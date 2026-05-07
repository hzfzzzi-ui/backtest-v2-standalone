## ADDED Requirements

### Requirement: 执行边界残留清理必须以正式替代路径稳定为前提
系统 SHALL 仅在正式共享执行边界替代路径已落地、文档已切换、回归已通过的前提下，清理旧过渡合同和重复 helper。

#### Scenario: 未满足替代条件时不得清理
- **WHEN** 某个旧合同仍被正式共享边界或主路径调用
- **THEN** 系统 MUST 不得将其纳入残留清理

### Requirement: 执行边界残留清理必须具备回退路径
系统 SHALL 为每一类执行边界残留清理定义最小回退路径，确保 cleanup 失败时可恢复到上一稳定状态。

#### Scenario: cleanup 失败时可回退
- **WHEN** 某次残留清理导致正式共享边界回归失败
- **THEN** 系统 MUST 有明确的回退步骤
