## Why

`v2-backend-boundary-freeze` 已经把公开 API、数据库访问、审计写盘和 foundation shell 定死，但 `backtest_v2.py` 里仍保留一小批公开旧壳：`/api/backtest_v2/results/{run_id}`、`_read_result()`、以及不再参与主链的兼容 helper。继续保留它们只会让旧表面长期存活，妨碍后续 retirement。

## What Changes

- 删除公开旧读取路由 `/api/backtest_v2/results/{run_id}`
- 删除仅供该旧读取路由使用的 `_read_result()` 兼容壳
- 删除已无 live caller 的 `_resolve_experiment_dir()`、`_preview_rejected_fields()`、`_load_runtime_cfg_obj()` 等空转 helper
- 清理对应 imports、测试和运维文档，形成 wave1 public shell retirement ledger
- 保持 `config_json -> experiment_id -> manifest/artifact` 主表面不变

## Capabilities

### New Capabilities
- `public-shell-retirement`: 分波次退役已经冻结且无 live caller 的公开旧壳

### Modified Capabilities
- `artifact-protocol-convergence`: 删除 legacy `/results/{run_id}` 读取面，只保留 manifest 驱动的实验产物访问
- `experiment-history`: 明确实验读取主面围绕 `experiment_id + manifest`，不再兼容旧 result payload

## Impact

- 影响代码：
  - `backend/api/endpoints/backtest_v2.py`
  - `tests/unit/test_public_surface_convergence.py`
  - `docs/ops/*retirement*`
- 影响系统：
  - 公开实验读取 API
  - 旧 result payload 兼容壳
