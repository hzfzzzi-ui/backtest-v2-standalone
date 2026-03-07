# V2 Baseline Lock And Regression

## What
Lock the March 7 baseline to experiment `exp_20260307_051743747_77d8` and add a repeatable regression contract that every cleanup change must pass before merge.

## Why
Cleanup without a locked baseline will drift behavior. The earlier built-in champion config was not the actual winning run. The validated baseline is the experiment artifact set produced from `HS300_ZZ500` / `000906.SH` with 800 raw symbols and 519 tradable symbols.

## Current State
- There is confusion between built-in champion configs and the real accepted baseline
- Cleanup changes do not yet have a required regression gate
- Different teams/scripts may compare against different experiments or configs

## Scope
- Declare `exp_20260307_051743747_77d8` as the single cleanup baseline
- Define the authoritative artifact set for regression
- Define acceptable equality rules for metrics and files
- Provide an operator workflow for rerun/compare verification

## Non-Goals
- No engine behavior changes
- No config governance redesign in this change
- No new strategy features

## Capabilities
### New Capabilities
- `baseline-regression-gate`: cleanup work can be validated against a stable experiment contract before and after each change

### Modified Capabilities
- `single-run-pipeline`: baseline verification becomes a required acceptance path for cleanup work

## Impact
- Experiment verification workflow
- Documentation of baseline truth
- Any future cleanup proposal referencing V2 behavior
