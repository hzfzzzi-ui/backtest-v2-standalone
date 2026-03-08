## ADDED Requirements

### Requirement: internal helper 不得依赖 config governance endpoint shim
系统 SHALL 保证 internal script helper 不依赖 `backend.api.endpoints._config_governance`。

#### Scenario: internal helper 依赖下沉
- **WHEN** internal helper 需要读取 saved config record
- **THEN** 它 MUST 通过 core helper 完成，而不是 import endpoint shim
