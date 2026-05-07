## Design

The shared account execution runtime remains the only owner for `risk_on -> defensive` transition execution. This change adds the second half of that behavior family:

1. sell-first release from risk-on holdings
2. immediate defense establish using released cash into the configured defense symbol

Scope is intentionally narrow:
- only `risk_on -> defensive`
- only defense establish after shared release
- no recovery-family behavior
- no new local weak-state owner

Implementation notes:
- policy carries `defense_establish_enabled`
- ETF precompute reads it into provider attrs
- execution path appends a shared defense buy signal after release plan activation
- candidate planning allows held-defense top-up for this execution path
