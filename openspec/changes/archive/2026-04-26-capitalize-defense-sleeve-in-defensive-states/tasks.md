## Tasks
- [x] 1.1 Align formal ETF phase1 limited-defense candidate to `511010.SH`
- [x] 1.2 Remove `511010.SH` from formal excluded scope and keep defensive-state target mapping coherent
- [x] 2.1 Update unit-test expectations for formal phase1 defense asset and summary/audit outputs
- [x] 2.2 Update compiler/runtime expectation tests that still treat `512890.SH` as formal limited defense
- [x] 3.1 Run focused unit tests for ETF contract / compiler / audit paths

## Rollback
- revert `backend/core/config/etf_beta/defaults.py`
- revert formal-defense expectation updates in `tests/unit/*`
- remove this change directory if abandoning the change

