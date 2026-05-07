# Residual Cleanup Batch 2026-04-04

## Batch Info
- `change`: `cleanup-post-refactor-residual-files`
- `validated_at`: `2026-04-04`
- `validated_by`: `Codex`

## Completed Now

### Frontend
- `frontend/assets/js/api.js`
- `frontend/assets/js/ui.js`
- `frontend/assets/js/compare.js`
- `frontend/app/results-workbench/components/AgentReportPanel.vue`
- `frontend/assets/js/results-workbench-bridge.js`
- `frontend/assets/js/artifacts.js`
- `frontend/assets/js/ui-controls.js`
- `frontend/assets/js/pages/desktop-config-controls.js`
- `frontend/assets/js/pages/desktop-history-panel.js`
- `frontend/assets/js/pages/desktop-research-page.js`

### Shared Execution Boundary
- 正式运行 payload 不再写出 `execution_intent`
- `mobile_cash_pool_service` 不再读取 `execution_intent`
- `sim_account_reconcile_service` 不再透传 `execution_intent`
- 主 spec 与测试不再把 `ExecutionIntent / CandidateBoundary / CandidatePlan` 视为正式合同

### Transactions / Sim Account
- `backend/core/services/transaction_lifecycle_service.py` 已切为 DB 主读写
- `backend/core/services/sim_account_domain_service.py` 已切为 DB 主读写
- `backend/core/services/sim_account_service.py` 的 holdings 主读写已切到 DB
- 正式对象已落到：
  - `public.pams_transaction_lifecycle`
  - `public.pams_sim_accounts`
  - `public.pams_sim_holdings_snapshots`
  - `public.pams_sim_cash_ledger`
  - `public.pams_sim_sync_logs`
  - `public.pams_sim_reconcile_summaries`
- `outputs/mobile_ops/*` 与 `outputs/ops/sim_account/*` 当前降级为影子写出 / 兼容回退，不再是正式主读路径

## Keep As Compat

### Legacy Desktop Bootstrap
- `frontend/assets/js/backtest_v2.js`

Reason:
- 新桌面壳边界已立住，但旧 bootstrap 尚未完全退出

### Internal Transitional Structures
- `backend/core/stage_pipeline/contracts.py :: CandidateBoundary* / CandidatePlan*`

Reason:
- 已不再作为运行时、测试或主 spec 的正式合同
- 当前仅保留在单文件内作为未导出的内部残留结构
- 后续可在更彻底的 stage payload 收口后直接删除

## Validation Notes
- 运行主链已无 `execution_intent` 读写残留
- 测试与主 spec 已切到当前正式执行边界
- 宿主机 compat 回归通过：`28 passed`
- 容器内真实 DB 已验证写入事务域正式对象
- 仍有条件依赖的对象未被误删

## Rollback Notes
- 若需回退 `5.3`，恢复：
  - `backend/core/stage_pipeline/adapters/order_planning.py`
  - `backend/core/services/mobile_cash_pool_service.py`
  - `backend/core/services/sim_account_reconcile_service.py`
  - `tests/unit/test_stage_adapter_split.py`
  - `tests/unit/test_stage_pipeline_extension_registry.py`
  - `openspec/specs/execution-contract-goldens/spec.md`
- 若需回退 `5.2`，恢复：
  - `backend/core/services/ops_domain_pg.py`
  - `backend/core/services/transaction_lifecycle_service.py`
  - `backend/core/services/sim_account_domain_service.py`
  - `backend/core/services/sim_account_service.py`
