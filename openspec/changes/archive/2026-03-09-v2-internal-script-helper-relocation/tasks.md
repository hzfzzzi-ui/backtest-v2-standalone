## 1. Relocation

- [x] 1.1 将 `backend/core/tools/internal_script_helper.py` 迁移到 `backend/scripts/_internal_helper.py`，并更新 scripts/tests import；DoD: 所有 caller 改到新路径；验证: `py_compile + direct harness`；风险: 漏改脚本引用
- [x] 1.2 删除旧的 `backend/core/tools/internal_script_helper.py`；DoD: `backend/core` 中不再保留该 helper；验证: grep；风险: 残留 caller

## 2. Guardrails

- [x] 2.1 更新 targeted tests 与 ops ledger，阻止 helper 回流到 core；DoD: 新测试覆盖 source 引用与 `backend/core` 零 endpoint 反向依赖；验证: direct harness；风险: 仅验证边界，不验证脚本全量运行
- [x] 2.2 运行 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`，确认 `exp_20260308_021045840_cde0` 核心产物继续 `PASS`；DoD: 仅允许 `report.html` 诊断性 `WARN`；验证: baseline compare；风险: helper relocation 误伤脚本基线门禁
