## Why
Current defensive-state account budgets already declare `511010.SH` as the defense asset, but the formal phase1 ETF sleeve still treats `512890.SH` as the only limited defense candidate and excludes `511010.SH` from formal scope. This leaves defense sleeve behavior split across explain, transition one-off orders, and formal selection scope.

## What Changes
- promote `511010.SH` to the formal limited-defense asset for governed ETF phase1
- remove the formal-scope exclusion that blocks `511010.SH` from becoming stable capital in defensive states
- align formal defense weights, formal scope, and weak-state target mapping so `TRANS_DOWN` / `RISK_OFF` can continuously hold defense capital

## Impact
- behavior change for governed ETF sleeve in `TRANS_DOWN` and `RISK_OFF`
- formal phase1 defense capital shifts from dividend-low-vol proxy to bond defense asset
- audit / summary / tests that assumed `512890.SH` as formal limited defense must be updated
