## Why
`511010.SH` has been formalized as the defensive asset, but recent 2023-2026 verification shows it still does not exist as a capital-real defense sleeve. At the same time, unified combo daily outputs can fall back to reference-only 50/50 state output, which weakens explainability and blocks state-conditioned analysis.

## What Changes
- default unified combo runtime to account-layer budget control when the combo payload omits an explicit control block
- add a formal defensive-state minimum defense exposure floor for `TRANS_DOWN` and `RISK_OFF`
- make ETF weak-state execution consume the defense floor so `511010.SH` becomes a persistent capital layer, not an occasional edge order
- ensure combo daily artifacts write effective account state from the account-layer path instead of empty/fallback state fields

## Impact
- L3 runtime behavior change for unified stock+ETF combo and ETF defensive-state allocation
- should improve explainability and enable state-conditioned occupancy analysis
