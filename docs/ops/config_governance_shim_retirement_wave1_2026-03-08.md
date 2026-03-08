# Config Governance Shim Retirement Wave1 (2026-03-08)

## 结论

wave1 删除了 [`_config_governance.py`](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/_config_governance.py) 这层旧 endpoint helper，并将 saved config access 与 runtime config source resolution 下沉到 [`saved_config_access.py`](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/tools/saved_config_access.py)。

本 wave 不改公开 `/api/backtest_v2/configs*` surface，不改 `config_json` 公开真相，不改回测计算核。

## live caller 证据

删除前代码盘点命令：

```powershell
Get-ChildItem -Recurse backend,frontend,tests -Include *.py,*.js,*.ts |
  Select-String -Pattern '_config_governance|resolve_runtime_config_source\(|load_saved_config_record\(|create_saved_config_record\(|write_saved_config_record\(|normalize_saved_config_record\('
```

删除前 live caller 仅包括：

- `backend/api/endpoints/_config_store.py`
- `backend/api/endpoints/_experiment_runner_api.py`
- `backend/core/tools/internal_script_helper.py`
- 少量测试文件

## 删除前置条件

- `_config_governance.py` 不承载公开路由
- `_config_store.py` 只需要 shared config helper，不依赖 endpoint shim 身份
- `_experiment_runner_api.py` 只消费 `resolve_runtime_config_source`
- `internal_script_helper.py` 只消费 `load_saved_config_record`

## 删除后保护

- active backend source 不得再引用 `_config_governance`
- `internal_script_helper.py` 不得再 import endpoint shim
- baseline gate 必须继续对 `exp_20260308_021045840_cde0` 保持核心 compare `PASS`
