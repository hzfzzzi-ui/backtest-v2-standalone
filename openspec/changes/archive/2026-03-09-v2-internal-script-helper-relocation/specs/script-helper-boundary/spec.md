## ADDED Requirements

### Requirement: 脚本专用 helper 不得位于 core
系统 SHALL 将仅供脚本/诊断工具使用的 helper 放在脚本或 support 层，而不是 `backend/core` 中。

#### Scenario: internal helper relocation
- **WHEN** internal script helper 只服务 scripts/tests
- **THEN** 它 MUST 位于脚本/support 层，且 `backend/core` 不得再持有该 helper
