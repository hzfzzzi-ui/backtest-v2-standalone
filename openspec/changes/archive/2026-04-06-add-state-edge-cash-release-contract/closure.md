# Closure

## Status
Closed as no-go on 2026-04-06.

## Why closed
The change implemented state-edge cash-release diagnostics and execution hooks, but repeated replay validation did not produce material behavior change.

Observed outcome:
- state-edge cash-release logic entered the runtime path
- combo and ETF standalone metrics remained unchanged
- primary outcomes remained reject-only, dominated by `ETF_BETA_STATE_EDGE_CASH_RELEASE_REJECT_NO_LIQUID_RELEASE` and `ETF_BETA_STATE_EDGE_CASH_RELEASE_REJECT_NO_RELEASE_REQUIRED`
- no stable `ACTIVE` or `PARTIAL_RELEASE_ACTIVE` behavior emerged in accepted replay validation

## Conclusion
This change did not clear the intended acceptance bar of improving weak-state executable behavior through partial de-risk cash release.

The research result is still useful:
- it eliminated timing-gate ambiguity
- it narrowed the next blocker to higher-level account allocation/runtime cutover instead of isolated ETF execution hooks

## Follow-up
Do not sync this delta spec into main specs as a completed capability.
Proceed with `cutover-to-account-allocation-runtime` instead.
