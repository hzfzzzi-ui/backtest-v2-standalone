## Design

This change capitalizes defense sleeve at the formal ETF phase1 layer instead of relying on transition-only behavior.

Implementation scope:
1. formal limited defense candidate becomes `511010.SH`
2. `511010.SH` is removed from formal phase1 excluded scope
3. phase1 defense bucket weights allocate to `511010.SH`
4. weak-state target mapping remains anchored to `511010.SH + 510300.SH`, but now matches formal scope and can persist across defensive states

Explicit non-goals:
- no new state-machine logic
- no change to stock alpha sleeve
- no new ETF symbols
- no always-invested experiment logic

Expected result:
- `TRANS_DOWN` / `RISK_OFF` governed ETF sleeve can hold bond defense as a continuous capital layer
- defense sleeve stops being explain-only / transition-only and becomes part of formal persistent allocation
