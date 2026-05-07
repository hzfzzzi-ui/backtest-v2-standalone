## Tasks
- [x] 1.1 Default unified combo runtime to enabled account-layer budget control when omitted by payload
- [x] 1.2 Ensure combo daily writes account-layer effective state fields instead of empty/fallback-only values
- [x] 2.1 Emit a formal `minimum_defense_exposure_floor` from ETF exposure semantics in `TRANS_DOWN` and `RISK_OFF`
- [x] 2.2 Consume the defense floor in ETF weak-state execution so defense deploy persists beyond edge-only behavior
- [x] 3.1 Run focused unit tests for unified runtime / ETF contract paths
- [x] 3.2 Re-run 2023-2026 unified combo and measure `511010.SH` capital occupancy in `TRANS_DOWN` and `RISK_OFF`

## Rollback
- revert unified runtime budget-control defaulting in `backend/core/services/cn_stock_etf_unified_runtime_service.py`
- revert defense-floor emission/consumption in ETF config+execution files
- remove this change directory if abandoning the change
