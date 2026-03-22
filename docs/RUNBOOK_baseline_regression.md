# RUNBOOK_baseline_regression

## 1. 目的

该 runbook 用于本仓库的 `P0/P1` 主线回归检查。

正式锚点:

- baseline: `baseline_V10.1`
- linked exp: `exp_20260314_144548534_7db9`

## 2. 执行顺序

### 2.1 默认 collect

```bash
pytest -q --collect-only
```

预期:

- 默认测试集至少能完成 collect

### 2.2 关键治理门

```bash
pytest -q tests/unit/test_script_surface_governance.py tests/unit/test_cli_main.py
pytest -q tests/unit/test_frontend_owner_boundaries.py tests/unit/test_frontend_runtime_boundaries.py
pytest -q tests/unit/test_api_compat_boundaries.py
```

### 2.3 主线回归门

```bash
python -m backend.cli audit --target baseline_regression
```

预期:

- 返回 `PASS`
- 不得出现 signal timing / execution timing / trade rule / universe definition
  的非预期漂移

## 3. 失败时处理

- `collect` 失败: 先修正式入口、导入面、脚本治理，不进入后续 apply
- 治理门失败: 先修边界漂移，不接受前端或 API 的“临时兜底”
- baseline 回归失败: 整波回退，先确认是否碰到了研究口径

## 4. 相关文档

- `docs/architecture_closure_gates.md`
- `docs/SCHEMA_run_meta.json.md`
- `docs/SCHEMA_manifest.json.md`
- `examples/experiment_contract_minimal/`
