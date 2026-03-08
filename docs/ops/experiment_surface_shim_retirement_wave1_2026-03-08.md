# Experiment Surface Shim Retirement Wave1 (2026-03-08)

## 结论

wave1 删除了 [`_experiment_surface.py`](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/_experiment_surface.py) 这层旧 API shim，并将共享 helper 下沉到 [`experiment_artifact_access.py`](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/tools/experiment_artifact_access.py)。

本 wave 不改公开 manifest 协议，不改 internal-only `results_dir` 能力，不改回测计算核。

## live caller 证据

删除前代码盘点命令：

```powershell
Get-ChildItem -Recurse backend,tests -Include *.py |
  Select-String -Pattern 'backend\.api\.endpoints\._experiment_surface|from \.?_experiment_surface|import _experiment_surface'
```

删除前仅命中：

- `backend/api/endpoints/backtest_v2.py`
- `backend/api/endpoints/_experiment_history.py`
- `backend/core/tools/internal_script_helper.py`

事实：未发现其他 active backend caller。

## 删除前置条件

- `backtest_v2.py` 仅把它用于 experiment 目录、manifest 与 declared artifact path 访问
- `_experiment_history.py` 仅把它用于 history/compare/report 的 manifest 驱动读面
- `internal_script_helper.py` 仅把它用于 internal-only results_dir/manifest helper

这些能力都可无损下沉到 core shared helper。

## 删除后保护

- active backend source 不得再引用 `_experiment_surface`
- `internal_script_helper.py` 不得再 import API endpoint shim
- baseline gate 必须继续对 `exp_20260308_021045840_cde0` 保持核心 compare `PASS`
