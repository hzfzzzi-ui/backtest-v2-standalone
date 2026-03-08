## 1. Shared state and route split
- [x] 1.1 Extract shared runtime state and route resolution from `legacy_adapter.py` into internal helper modules without changing public entrypoints.
- [x] 1.2 Add focused unit coverage for route resolution and shared runtime preparation behavior.

## 2. Stage responsibility split
- [x] 2.1 Extract candidate flow stage logic (`S1`-`S6`) into a dedicated internal module.
- [x] 2.2 Extract holding flow stage logic (`S9`-`S8`) into a dedicated internal module.
- [x] 2.3 Extract `S7` order planning glue into a dedicated internal module and keep result parity.

## 3. Verification and freeze
- [x] 3.1 Run targeted adapter tests plus `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate` and confirm the locked baseline remains equivalent.
- [x] 3.2 Document the new internal module ownership and mark the monolithic adapter layout as frozen.
