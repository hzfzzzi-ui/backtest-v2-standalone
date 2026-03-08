## Why

`_candidate_presets.py` 当前不承载公开路由，只提供 locked candidate preset 的共享 helper。事实是它的 live caller 仅包括：

- `backend/api/endpoints/_experiment_runner_api.py`
- `backend/core/tools/internal_script_helper.py`
- 一个 internal script

继续把这层 helper 放在 endpoint 目录，会让 internal script 与 API orchestrator 继续依赖 endpoint shim。

## What Changes

- 将 `_candidate_presets.py` 的共享 helper 下沉到 `backend/core/tools`
- 更新 `_experiment_runner_api.py` 与 `internal_script_helper.py`
- 删除 `_candidate_presets.py`
- 补 wave1 ledger、回流测试与 baseline gate

## Capabilities

### New Capabilities
- `locked-candidate-access-boundary`: locked candidate preset 共享逻辑必须位于 core helper，不得由 endpoint shim 承载

### Modified Capabilities
- `single-run-pipeline`: locked candidate preset 分支继续工作，但 helper 实现迁移到 core
- `internal-shim-boundary`: internal helper 不得依赖 `backend.api.endpoints._candidate_presets`
