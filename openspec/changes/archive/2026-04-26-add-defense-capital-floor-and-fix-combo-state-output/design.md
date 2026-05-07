## Scope
This is a minimal L3 continuation focused on two issues already observed in live artifacts:
1. combo daily/account state output can fall back to reference-only fields and lose account-layer state visibility
2. weak-state defense exists in formal scope but lacks a persistent exposure floor, leaving `511010.SH` undercapitalized

## Design
1. Unified combo runtime
- If `unified_runtime.account_budget_control` is absent, synthesize an enabled default using 50/50 fallback weights so account-layer daily resolution still runs.
- Combo daily should always emit `account_budget_effective_state_5`, `account_state_source`, and `account_transition_kind` from the account-layer daily budget frame when available.

2. ETF defense floor
- Exposure semantics will emit a new `minimum_defense_exposure_floor` for defensive states.
- The floor equals the formal limited-defense budget already implied by weak-state targets.
- ETF execution consumes this floor between rebalances. If current defense exposure is below the floor, weak-state deploy uses the defense symbols and the defense gap rather than only opportunistic transition edge behavior.

3. Non-goals
- no new symbols
- no new state-machine logic
- no always-invested experiment
- no stock alpha changes
