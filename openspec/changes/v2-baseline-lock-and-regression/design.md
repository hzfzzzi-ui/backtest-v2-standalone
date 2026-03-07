# Design: Baseline Lock And Regression

## Context
The accepted baseline is not a built-in config file but the experiment artifacts under `outputs/experiments/exp_20260307_051743747_77d8`. This experiment reflects the real March 7 champion run the user wants to preserve during cleanup.

Key baseline facts:
- `universe_mode = HS300_ZZ500`
- `symbols_source = pit_index_constituents`
- `raw_count = 800`
- `tradable_symbols = 519`
- `benchmark = 000300.SH`
- `date range = 2016-03-01 .. 2026-03-01`
- `cagr = 0.0635482026379195`
- `max_drawdown = -0.47180753475805515`
- `sharpe = 0.3638706027515262`
- `trades = 61`

## Goals / Non-Goals
**Goals:**
- create one baseline truth for all cleanup changes
- define file-level and metric-level regression checks
- standardize how a rerun is compared to the locked baseline

**Non-Goals:**
- generate a new champion
- bless alternative “close enough” baselines
- audit all historical experiments

## Decisions
### D1: Baseline artifact set
The required comparison set is:
- `run_meta.json`
- `run_config.json`
- `perf.json`
- `nav.csv`
- `portfolio_trades.csv`
- `report.html`

### D2: Equality policy
For cleanup changes, acceptance requires:
- metric equality for `cagr`, `max_drawdown`, `sharpe`, `trades`, `total_return`
- same start/end dates and universe summary in `run_meta.json`
- same row count and last value in `nav.csv`
- same trade count and reason-code distribution in `portfolio_trades.csv`

### D3: Verification workflow
Every change that touches frontend config handling, API compilation, engine routing, or universe resolution must rerun the baseline and compare against the locked artifact set before continuing to the next cleanup step.

### D4: Reporting requirement
Each cleanup change should record whether the baseline passed unchanged or where drift appeared. Drift blocks progress to the next cleanup stage.

## Alternatives Considered
1. Use the latest built-in champion config as baseline. Rejected because it is not the validated March 7 experiment.
2. Compare only summary metrics. Rejected because config/report drift can occur while headline metrics stay similar.
3. Allow tolerance bands. Rejected for architecture cleanup because no intentional behavior change is allowed.
