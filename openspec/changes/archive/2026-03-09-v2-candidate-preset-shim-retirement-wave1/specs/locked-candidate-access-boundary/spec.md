## ADDED Requirements

### Requirement: locked candidate preset 共享逻辑必须位于 core helper
系统 SHALL 将 locked candidate preset 的共享逻辑放在 core helper 中，而不是 endpoint shim 中。

#### Scenario: live callers 迁移到 core helper
- **WHEN** `_experiment_runner_api.py` 或 internal helper 需要 locked candidate preset helper
- **THEN** 它们 MUST 依赖 core helper，而不是 `backend.api.endpoints._candidate_presets`
