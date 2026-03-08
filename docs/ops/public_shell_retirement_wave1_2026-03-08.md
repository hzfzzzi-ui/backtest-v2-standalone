# Public Shell Retirement Wave1 (2026-03-08)

## 结论

wave1 删除了 `backtest_v2.py` 中已经冻结且无 live caller 的公开旧结果壳：

- `/api/backtest_v2/results/{run_id}`
- `_read_result()`
- `_resolve_experiment_dir()`
- `_preview_rejected_fields()`
- `_load_runtime_cfg_obj()`
- `_list_recent_experiments()`

本 wave 不触碰内部 `results_dir` shim，也不改变 `config_json -> experiment_id -> manifest/artifact` 主表面。

## 零调用证据

2026-03-08 代码盘点命令：

```powershell
Get-ChildItem -Recurse backend,frontend,tests -Include *.py,*.js,*.ts |
  Select-String -Pattern 'get_backtest_v2_result|_read_result\(|_resolve_experiment_dir\(|_preview_rejected_fields\(|_load_runtime_cfg_obj\('
```

盘点结果仅命中：

- `backend/api/endpoints/backtest_v2.py:260` `_resolve_experiment_dir(...)`
- `backend/api/endpoints/backtest_v2.py:271` `_preview_rejected_fields(...)`
- `backend/api/endpoints/backtest_v2.py:358` `_load_runtime_cfg_obj()`
- `backend/api/endpoints/backtest_v2.py:363` `_read_result(...)`
- `backend/api/endpoints/backtest_v2.py:800` `get_backtest_v2_result(...)`
- `backend/api/endpoints/backtest_v2.py:804` `payload = _sanitize_for_json(_read_result(out_dir))`

事实：未发现 backend、frontend、tests 内的其他 live caller。

## 删除前置条件

- 公开读面已固定为 `experiment_id + manifest + declared artifacts`
- artifact read public contract 已禁止 `results_dir`
- experiment history / compare / report 已围绕 manifest 工作
- 前端已不再请求 `/api/backtest_v2/results/{run_id}`

## 删除后保护

- 定向测试断言 `/api/backtest_v2/results/{run_id}` 不再注册
- 定向测试断言同批 helper 不再出现在 `backtest_v2` 模块
- baseline gate 必须继续对 `exp_20260308_021045840_cde0` 保持核心产物 `PASS`

## 不在本 wave 删除的内容

- `_experiment_surface.py` 内部 `results_dir` 兼容能力
- `internal_script_helper.py` 里的内部 shim
- experiment history / compare / report 的 manifest 主链
