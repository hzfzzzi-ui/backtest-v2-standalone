## ADDED Requirements

### Requirement: saved config access 共享逻辑必须位于 core helper
系统 SHALL 将 saved config record 的规范化、读写与 runtime config source resolution 放在 core/shared helper 中，而不是 endpoint shim 中。

#### Scenario: live callers 迁移到 core helper
- **WHEN** `_config_store.py`、`_experiment_runner_api.py`、`internal_script_helper.py` 需要 saved config helper
- **THEN** 它们 MUST 依赖 core helper，而不是 `backend.api.endpoints._config_governance`
