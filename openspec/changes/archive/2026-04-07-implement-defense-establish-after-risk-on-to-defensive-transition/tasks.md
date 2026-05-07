## Tasks
- [x] 1.1 Extend shared transition policy with defense establish enablement
- [x] 1.2 Read defense establish policy in ETF precompute
- [x] 2.1 Append shared defense establish buy signal after sell-first release
- [x] 2.2 Allow held defense top-up for shared transition execution path
- [x] 3.1 Replay ETF standalone and verify shared defense establish orders appear
- [x] 3.2 Replay `A_STOCK_ETF_V1` and compare metrics plus order reasons

## Rollback
- revert `backend/core/services/account_allocator_shadow.py`
- revert `backend/core/services/cn_stock_etf_unified_runtime_service.py`
- revert `backend/core/engine_vector/etf_beta/selection.py`
- revert `backend/core/engine_vector/etf_beta/execution_paths.py`
- revert `backend/core/portfolio/candidate_plan.py`

