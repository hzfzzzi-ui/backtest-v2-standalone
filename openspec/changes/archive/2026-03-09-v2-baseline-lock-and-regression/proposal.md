# V2 Baseline Lock And Regression

## What
Lock the March 7 baseline to experiment `exp_20260307_051743747_77d8` and add a repeatable regression contract that every cleanup change must pass before merge.

## Why
Cleanup without a locked baseline will drift behavior. The earlier built-in champion config was not the actual winning run. The validated baseline is the experiment artifact set produced from `HS300_ZZ500` / `000906.SH` with 800 raw symbols and 519 tradable symbols, but the cleanup contract must also preserve the resolved runtime input bundle that produced those outputs.

## Current State
- There is confusion between built-in champion configs and the real accepted baseline
- Cleanup changes do not yet have a required regression gate
- The accepted baseline is an experiment artifact set, not just a built-in config file
- Different teams/scripts may compare against different experiments or configs
- `report.html` consistency is being improved in a separate change and should not be treated as a raw byte-for-byte golden file

## Scope
- Declare `exp_20260307_051743747_77d8` as the single cleanup baseline
- Define the authoritative baseline input bundle and output artifact set
- Define acceptable equality rules for metrics and files
- Define how to classify drift caused by code changes vs data/environment changes
- Distinguish blocking drift from diagnostic-only drift so the gate can report `PASS / WARN / FAIL`
- Provide an operator workflow for rerun/compare verification

## Non-Goals
- No engine behavior changes
- No config governance redesign in this change
- No new strategy features
- No blessing of alternative “close enough” baselines

## Capabilities
### New Capabilities
- `baseline-regression-gate`: cleanup work can be validated against a stable experiment contract before and after each change
- `baseline-input-bundle`: the baseline is preserved as both an output artifact set and a resolved runtime input truth

### Modified Capabilities
- `single-run-pipeline`: baseline verification becomes a required acceptance path for cleanup work
- `report-consistency-contract`: report validation for baseline cleanup uses semantic field comparison rather than raw HTML equality

## Impact
- Experiment verification workflow
- Documentation of baseline truth
- A reusable baseline regression script for self-check, candidate compare, and rerun compare
- Cleanup sequencing and merge gates for all V2 refactors
