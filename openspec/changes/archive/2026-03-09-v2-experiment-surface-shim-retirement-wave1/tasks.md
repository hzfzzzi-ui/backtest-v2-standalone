## 1. Wave1 Evidence

- [x] 1.1 固化 `_experiment_surface.py` 的 live caller 仅为 `backtest_v2.py`、`_experiment_history.py`、`internal_script_helper.py` 的证据与删除前置条件；DoD: 形成 wave1 ledger；验证: grep/文档审阅；风险: 漏掉隐式调用者

## 2. Shared Helper Migration

- [x] 2.1 新建 core 级 experiment artifact access helper，并迁移 `backtest_v2.py`、`_experiment_history.py`、`internal_script_helper.py`；DoD: 三个 live caller 均改用 core helper；验证: `py_compile + direct harness`；风险: helper 行为偏移
- [x] 2.2 删除 `_experiment_surface.py`；DoD: active backend source 不再引用该 shim；验证: grep；风险: 残留 caller

## 3. Guardrails

- [x] 3.1 更新 targeted tests 与 ops ledger，阻止 `_experiment_surface.py` 回流；DoD: 新测试覆盖无 source 引用与 internal helper 边界；验证: direct harness；风险: 仅验证删除，不验证主表面可用
- [x] 3.2 运行 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`，确认 `exp_20260308_021045840_cde0` 核心产物继续 `PASS`；DoD: 仅允许 `report.html` 诊断性 `WARN`；验证: baseline compare；风险: seemingly unrelated helper relocation 误伤产物链路
