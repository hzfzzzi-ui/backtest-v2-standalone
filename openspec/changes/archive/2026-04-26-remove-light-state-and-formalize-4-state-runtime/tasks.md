## 1. 4-state 正式化
- [x] 1.1 账户层与主状态机移除 `LIGHT` 正式输出，只保留兼容别名
- [x] 1.2 ETF 正式状态映射与模板删除 `LIGHT`

## 2. 输出收口
- [x] 2.1 runtime / query / audit / front-end 不再把 `LIGHT` 当正式状态
- [x] 2.2 历史 `LIGHT` 输入兼容映射到 `TRANS_UP`

## 3. 最小验证
- [x] 3.1 运行主回放并确认新产物无正式 `LIGHT`
  - 结论：已用 `CN_STOCK_ETF_FORMAL_V1 -> exp_20260426_005716047_8650` 的正式产物完成 artifact-verified 闭环，见 `verification_3_1_artifact_check.md`。
  - 备注：宿主机直连环境仍无法解析 `pams-postgres`，因此本条不是 environment-replayed 结案。
- [x] 3.2 跑最小正式回归
  - 已通过：
    - `tests/unit/test_runtime_boundary_contracts.py`
    - `tests/unit/test_artifacts_finalize_regime_meta.py`
    - `tests/unit/test_market_regime_engine.py`
    - `tests/unit/test_attribution_audit.py`
    - `tests/unit/test_research_audit_contract.py::test_evaluate_attribution_traceability_passes_for_unified_combo_governor_snapshot`
    - `tests/unit/test_research_audit_contract.py::test_evaluate_attribution_traceability_passes_when_summary_and_refs_exist`
