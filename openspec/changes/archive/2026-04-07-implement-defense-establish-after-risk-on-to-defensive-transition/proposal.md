## Why
Shared account execution runtime already owns `risk_on -> defensive` sell-first cash release, but released cash is not yet connected to defense establish. This leaves the transition half-complete and keeps weak-state defensive positioning dependent on later local deploy paths.

## What Changes
- extend shared `risk_on -> defensive` execution with defense establish on the same edge
- allow released cash to drive immediate defense buy-side establish into `511010.SH`
- keep old weak-state local deploy paths as diagnostics/reference only on the same edge

## Impact
- behavior change on `risk_on -> defensive`
- expects attributable order-level drift
- should improve execution completeness without re-opening dual ownership
