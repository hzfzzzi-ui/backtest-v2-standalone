# API Compat Audit

Date: 2026-03-15

## Facts

- New formal HTTP surfaces live under:
  - `backend/api/backtest_v2/*`
  - `backend/api/mobile/*`
- Mobile routes now depend on `backend.api.mobile.impl`.
- `backend/api/endpoints/_mobile_dashboard_impl.py` is now a thin re-export shim over `backend.api.mobile.impl`.
- `backend/api/backtest_v2/contracts/requests.py` now defines public request models directly.
- `backend/api/endpoints/_public_contracts.py` now depends on the new contracts module instead of the reverse.

## Remaining Heavy Compat Carriers

- `backend/api/endpoints/_experiment_runner_api.py`
- `backend/api/endpoints/_backtest_v2_impl.py`
- `backend/api/endpoints/_config_store.py`

These still carry heavy logic and are not yet thin shims.

## Dependency Direction After This Cleanup Slice

- Allowed:
  - `backend/api/endpoints/* -> backend/api/backtest_v2/*`
  - `backend/api/endpoints/* -> backend/api/mobile/*`
- Disallowed:
  - `backend/api/mobile/* -> backend/api/endpoints/*`
  - `backend/api/backtest_v2/contracts/* -> backend/api/endpoints/_public_contracts.py`

## Follow-up Targets

1. Continue shrinking `_experiment_runner_api.py` behind route/service boundaries.
2. Continue shrinking `_backtest_v2_impl.py` behind route/service boundaries.
3. Keep old HTTP paths, but keep moving implementation ownership out of `backend/api/endpoints/*`.

