# Proposal

## Summary

Implement the first behavior-ready transition family in the shared account execution runtime:

- `risk_on -> defensive`

This change moves the first real execution behavior under the account-layer transition contract instead of continuing to adapt old ETF weak-state local paths.

## Why

Current architecture already completed:

- account-layer steady-state budget ownership
- account-layer transition contract ownership
- shared account execution runtime ownership

But the first behavior family is still missing. As a result:

- old ETF local weak-state paths still generate the real sell-first behavior
- the shared account layer remains contract-only for transition execution

This change implements the first concrete behavior:

- on `risk_on -> defensive` transition edges
- establish bounded partial de-risk
- release defensive cash first
- suppress old ETF local edge owners on the same edge
