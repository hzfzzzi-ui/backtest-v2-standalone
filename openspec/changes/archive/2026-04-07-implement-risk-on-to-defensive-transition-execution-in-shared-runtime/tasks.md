# Tasks

## 1. Shared policy injection

- [x] 1.1 Add a formal config slot for shared transition execution in ETF sleeve semantic config.
- [x] 1.2 Inject the shared account transition execution policy into ETF sleeve input before ETF sleeve execution.

## 2. Behavior implementation

- [x] 2.1 Implement bounded partial de-risk for `risk_on -> defensive` in ETF execution.
- [x] 2.2 Demote old local edge owners to diagnostics-only on the same transition edge.

## 3. Validation

- [x] 3.1 Replay ETF standalone and confirm shared-runtime-owned sell-first behavior appears.
- [x] 3.2 Replay `A_STOCK_ETF_V1` and compare metrics plus transition-edge reason codes.

## 4. Rollback

- [x] 4.1 Document rollback file set and reason-code expectations.

Rollback files:

- `backend/api/backtest_v2/semantic_config_schema.py`
- `backend/core/services/account_allocator_shadow.py`
- `backend/core/services/cn_stock_etf_unified_runtime_service.py`
- `backend/core/engine_vector/etf_beta/selection.py`
- `backend/core/engine_vector/etf_beta/execution_paths.py`

Expected execution evidence:

- new sell-side reason code: `ETF_BETA_SHARED_ACCOUNT_TRANSITION_RISK_ON_TO_DEFENSIVE_ACTIVE`
- old local owner no longer owns the same edge as primary execution path
