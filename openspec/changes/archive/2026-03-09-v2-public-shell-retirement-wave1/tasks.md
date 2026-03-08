## 1. Wave1 Evidence

- [x] 1.1 固化 `/api/backtest_v2/results/{run_id}`、`_read_result()`、`_resolve_experiment_dir()`、`_preview_rejected_fields()`、`_load_runtime_cfg_obj()` 的零 live caller 证据与删除前置条件；DoD: 形成 wave1 ledger；验证: grep/文档审阅；风险: 漏掉隐式调用者

## 2. Public Shell Retirement

- [x] 2.1 删除 `/api/backtest_v2/results/{run_id}` 与 `_read_result()`；DoD: `backtest_v2.py` 不再暴露 legacy result payload；验证: router/path 定向检查；风险: 仍有外部调用者依赖旧 route
- [x] 2.2 删除 `_resolve_experiment_dir()`、`_preview_rejected_fields()`、`_load_runtime_cfg_obj()` 及对应废弃 import；DoD: `backtest_v2.py` 中不再保留这些空转 helper；验证: `py_compile + grep`；风险: 误删 residual caller

## 3. Guardrails

- [x] 3.1 更新 targeted tests 与 ops ledger，阻止 `/results/{run_id}` 与同批 helper 回流；DoD: 新测试覆盖路由不存在与主表面保持不变；验证: direct harness；风险: 仅验证删除，不验证主表面可用
- [x] 3.2 运行 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`，确认 `exp_20260308_021045840_cde0` 核心产物继续 `PASS`；DoD: 仅允许 `report.html` 诊断性 `WARN`；验证: baseline compare；风险: seemingly unrelated public cleanup 误伤产物链路
