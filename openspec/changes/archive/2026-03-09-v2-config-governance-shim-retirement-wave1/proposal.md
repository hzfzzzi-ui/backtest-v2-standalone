## Why

`_config_governance.py` 当前不承载任何公开 API，只提供 saved config record 与 runtime config source 的共享 helper。事实是它的 live caller 仅包括：

- `backend/api/endpoints/_config_store.py`
- `backend/api/endpoints/_experiment_runner_api.py`
- `backend/core/tools/internal_script_helper.py`
- 少量测试文件

继续把这层 helper 放在 `backend.api.endpoints` 下，会让 core helper 与 runtime pipeline 间接依赖 endpoint 模块，阻碍后端边界彻底收敛。

## What Changes

- 将 `_config_governance.py` 的共享 helper 下沉到 `backend/core/tools`
- 更新 `_config_store.py`、`_experiment_runner_api.py`、`internal_script_helper.py` 和测试改用新的 core helper
- 删除 `_config_governance.py`
- 补 wave1 ledger、回流测试与 baseline gate

## Capabilities

### New Capabilities
- `saved-config-access-boundary`: saved config record 与 runtime config source 共享逻辑必须位于 core helper，不得由 endpoint shim 承载

### Modified Capabilities
- `config-source-governance`: config source resolution 继续工作，但实现迁移到 core helper
- `internal-shim-boundary`: internal helper 不得依赖 `backend.api.endpoints._config_governance`

## Impact

- 影响代码：
  - `backend/core/tools/*`
  - `backend/api/endpoints/_config_store.py`
  - `backend/api/endpoints/_experiment_runner_api.py`
  - `backend/core/tools/internal_script_helper.py`
  - `tests/*`
- 影响系统：
  - saved config 访问与 runtime config source resolution
