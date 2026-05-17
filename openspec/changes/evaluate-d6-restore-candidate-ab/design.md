## Context

The D6 visibility audit found that some D5 half-exit positions later re-entered
the raw breakout candidate set, but they were removed by the provider-level
"already held" filter before candidate planning. This means the original entry
logic may already be capable of recognizing repair, while the runtime contract
prevents a half-sold position from being restored.

This change tests that hypothesis as a research-only AB. It does not change the
stock universe, ETF sleeve, ranking factor, D5 failure thresholds, combo
allocator, or NAV truth.

## Design

### Variants

- `B0_COMBO_V3_REPLAY`: replay the V3 stock+ETF combo template without D5 restore
  changes.
- `HC_D5_IMMEDIATE_COMBO`: high-chase D5 failures exit half immediately, with no
  restore candidate behavior.
- `HC_D5_IMMEDIATE_RESTORE_COMBO`: same D5 immediate half exit, plus
  `restore_candidate` when the same symbol later re-enters the raw breakout
  candidate set while the account still holds the remaining half position.

### Restore State

The provider arms restore state on partial sell fill only when all conditions are true:

- D5 MFE/MAE confirmation exit is enabled.
- The confirmation action creates a partial sell, not a full liquidation.
- The partial sell order is actually filled.
- The symbol remains held after the sell under normal runtime accounting.
- The restore experiment switch is enabled.

The state is symbol-scoped and expires after `mfe_mae_restore_candidate_max_bars`.
It is cleared when the symbol is fully exited or when a restore buy is filled.

### Candidate Semantics

A restore candidate is allowed only when the same symbol appears in the normal
raw buy candidate list again. It must keep the normal candidate score and pass the
same tradability, ranking, cash, lot, and execution checks as any other buy.

The signal carries:

- `restore_candidate=true`
- `restore_candidate_source=mfe_mae_confirmation_exit`
- `target_weight_basis=delta_restore_gap`
- `reason_code=MFE_MAE_RESTORE_CANDIDATE`

Candidate and execution planning may bypass the "already held" rejection only for
this explicit restore metadata. The buy quantity is capped to:

`normal_target_quantity - current_quantity`

rounded down by lot size. If the delta is not positive, the order is rejected.
Restore top-ups do not consume an additional symbol slot because the symbol is
already part of the portfolio.

### Outputs

The study must expose, at minimum:

- same-window performance metrics for all variants,
- restore candidate/order reason counts,
- candidate or execution rejects caused by zero delta, cash, lot, or tradability,
- experiment ids and effective execution start dates.

### Acceptance

The result is acceptable for further research only if:

- all variants use the same unified stock+ETF runtime NAV truth,
- `HC_D5_IMMEDIATE_RESTORE_COMBO` is comparable to `HC_D5_IMMEDIATE_COMBO` on the
  same windows,
- restore events are visible in diagnostics or reason-code counts,
- 2012-2017 does not materially fail relative to the no-restore D5 variant,
- the conclusion states whether any gain is broad enough to continue or only a
  small-sample artifact.

No baseline promotion is included in this change.

## Risks

- Restore events may be rare, so apparent improvements can be sample-sensitive.
- Letting a half-sold weak breakout restore may increase churn if the raw entry
  signal is noisy.
- If the delta quantity is not handled correctly, restore could accidentally
  overbuy an existing holding. Unit tests must cover this.
