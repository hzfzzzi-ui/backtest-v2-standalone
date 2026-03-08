## 1. Wave1 Evidence

- [x] 1.1 固化 `_config_governance.py` 的 live caller 与删除前置条件；DoD: 形成 wave1 ledger；验证: grep/文档审阅；风险: 漏掉隐式调用者

## 2. Shared Helper Migration

- [x] 2.1 新建 core 级 saved config access helper，并迁移 `_config_store.py`、`_experiment_runner_api.py`、`internal_script_helper.py` 与测试；DoD: 所有 live caller 改用 core helper；验证: `py_compile + direct harness`；风险: helper 行为偏移
- [x] 2.2 删除 `_config_governance.py`；DoD: active backend source 不再引用该 shim；验证: grep；风险: 残留 caller

## 3. Guardrails

- [x] 3.1 更新 targeted tests 与 ops ledger，阻止 `_config_governance.py` 回流；DoD: 新测试覆盖 no-source-reference 与 internal helper 边界；验证: direct harness；风险: 仅验证删除，不验证公开 config surface 可用
- [x] 3.2 运行 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`，确认 `exp_20260308_021045840_cde0` 核心产物继续 `PASS`；DoD: 仅允许 `report.html` 诊断性 `WARN`；验证: baseline compare；风险: helper relocation 误伤 config truth / manifest
