## ADDED Requirements

### Requirement: internal helper 不得依赖 candidate preset endpoint shim
系统 SHALL 保证 internal helper 不依赖 `backend.api.endpoints._candidate_presets`。

#### Scenario: internal helper 依赖下沉
- **WHEN** internal helper 需要访问 locked candidate preset helper
- **THEN** 它 MUST 通过 core helper 完成，而不是 import endpoint shim
