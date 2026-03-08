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

The baseline must preserve not only outputs, but also the resolved input truth that produced them.

## Goals / Non-Goals
**Goals:**
- create one baseline truth for all cleanup changes
- define both input-bundle and output-artifact regression checks
- standardize how a rerun is compared to the locked baseline
- distinguish code drift from environment/data drift

**Non-Goals:**
- generate a new champion
- bless alternative “close enough” baselines
- audit all historical experiments

## Decisions
### D1: Baseline input bundle
The locked baseline input bundle includes:
- experiment id `exp_20260307_051743747_77d8`
- the experiment directory contents
- resolved runtime metadata from `run_meta.json`
- resolved runtime config from `run_config.json`
- saved config provenance when available, including `cfg_d5bcddc928d1` and `config_conflict_policy`

This change treats the baseline as a resolved runtime truth, not just a preset name.

### D2: Baseline output artifact set
The required comparison set is:
- `run_meta.json`
- `run_config.json`
- `perf.json`
- `nav.csv`
- `portfolio_trades.csv`
- `report.html`

### D3: Equality policy
For cleanup changes, acceptance requires:
- metric equality for `cagr`, `max_drawdown`, `sharpe`, `trades`, `total_return`
- same start/end dates, benchmark, and semantic core in `run_meta.json`
- same universe summary in `run_meta.universe`
- same row count, endpoints, and file hash in `nav.csv`
- same trade count, reason-code distribution, and file hash in `portfolio_trades.csv`
- semantic equality for report summary fields rather than raw HTML byte equality
- saved-config provenance and report source diagnostics are compared separately from result artifacts

### D4: Environment and data notes
Because the runtime depends on PostgreSQL market/universe data, rerun verification must record whether a mismatch appears to come from:
- code drift
- saved-config resolution drift
- database/universe data drift
- report rendering drift
- report diagnostic drift

The baseline gate blocks cleanup progression unless that classification is explicit.

### D5: Verification workflow
Every change that touches frontend config handling, API compilation, engine routing, reporting, or universe resolution must rerun the baseline and compare against the locked input/output contract before continuing to the next cleanup step.

### D6: Reporting requirement
Each cleanup change should record whether the baseline returned:
- `PASS`: no mismatches
- `WARN`: only diagnostic-only mismatches such as saved-config provenance or report source diagnostics
- `FAIL`: at least one blocking mismatch in runtime or output artifacts

Only `FAIL` blocks progression to the next cleanup stage. `WARN` still requires explicit acknowledgement in the change notes.

## Alternatives Considered
1. Use the latest built-in champion config as baseline. Rejected because it is not the validated March 7 experiment.
2. Compare only summary metrics. Rejected because config/report drift can occur while headline metrics stay similar.
3. Treat `report.html` as a raw golden file. Rejected because report consistency is already governed semantically by existing report work.
4. Allow tolerance bands. Rejected for architecture cleanup because no intentional behavior change is allowed.
