# Candidate Preset Shim Retirement Wave1 (2026-03-08)

## 结论

wave1 删除了 [`_candidate_presets.py`](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/_candidate_presets.py) 这层旧 endpoint helper，并将 locked candidate preset 共享逻辑下沉到 [`locked_candidate_presets.py`](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/tools/locked_candidate_presets.py)。

本 wave 不改变 locked candidate preset 列表，不改变 candidate artifact 协议，不改变普通回测主链。

## live caller 证据

删除前代码盘点命令：

```powershell
Get-ChildItem -Recurse backend,tests -Include *.py |
  Select-String -Pattern '_candidate_presets|candidate_presets_api\(|build_locked_candidate_cfg\(|is_locked_candidate_preset\(|write_locked_candidate_artifacts\('
```

删除前 live caller 仅包括：

- `backend/api/endpoints/_experiment_runner_api.py`
- `backend/core/tools/internal_script_helper.py`
- `backend/scripts/run_clean_data_standard_reruns.py`

## 删除后保护

- active backend source 不得再引用 `_candidate_presets`
- `internal_script_helper.py` 不得再 import endpoint shim
- baseline gate 必须继续对 `exp_20260308_021045840_cde0` 保持核心 compare `PASS`
