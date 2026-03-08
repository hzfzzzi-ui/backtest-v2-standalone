## Why

`_experiment_surface.py` 当前只是一个旧 API endpoint shim，内部只承载实验目录、manifest、artifact path 解析等共享 helper。事实是它的 live caller 只有：

- `backend/api/endpoints/backtest_v2.py`
- `backend/api/endpoints/_experiment_history.py`
- `backend/core/tools/internal_script_helper.py`

继续保留这层会让 core 侧 helper 反向依赖 `backend.api.endpoints`，不利于把后端 API、引擎 pipeline、数据库接口、审计模块的边界彻底定死。

## What Changes

- 将 `_experiment_surface.py` 的共享 helper 下沉到 `backend/core/tools`
- 更新 `backtest_v2.py`、`_experiment_history.py`、`internal_script_helper.py` 改用新的 core helper
- 删除 `_experiment_surface.py`
- 增加 wave1 ledger、回流测试与基线门禁验证

## Capabilities

### New Capabilities
- `experiment-artifact-access-boundary`: 共享实验目录/manifest/artifact path 访问能力必须位于 core shared helper，不得由 API shim 承载

### Modified Capabilities
- `internal-shim-boundary`: internal helper 不得依赖 `backend.api.endpoints._experiment_surface`
- `experiment-history`: 实验历史与报告读取继续围绕 manifest 工作，但读取 helper 改由 core 提供

## Impact

- 影响代码：
  - `backend/core/tools/internal_script_helper.py`
  - `backend/api/endpoints/backtest_v2.py`
  - `backend/api/endpoints/_experiment_history.py`
  - `backend/api/endpoints/_experiment_surface.py`
- 影响系统：
  - 实验目录访问共享层
  - internal script helper 的模块依赖边界
