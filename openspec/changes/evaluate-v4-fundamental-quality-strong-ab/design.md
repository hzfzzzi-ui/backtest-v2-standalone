## Primary Variable

PIT fundamental quality is promoted from a weak ranking overlay to a stronger
candidate-selection assistant. The trend system still decides when a stock is a
candidate; quality only decides which eligible candidates deserve priority or
size when capital/slots are scarce.

## Data Contract

Use the already audited daily snapshot:

`outputs/studies/cn_stock/v4_fundamental_quality_ranking_ab_v1/snapshots/fundamental_quality_daily_snapshot.csv`

The snapshot contract remains:

- one row per date/symbol/factor;
- `quality_score` is computed only from rows with `ann_date <= date`;
- unavailable quality is not imputed into a fake high score.

## Variants

- `B0_V4_STOCK_REPLAY`: same V4 stock replay.
- `Q_BAND_RERANK_20`: quality can rerank a wider top-20 same-day candidate band.
- `Q_VETO_BOTTOM25`: veto the bottom 25% available-quality candidates of the
  same-day candidate set.
- `Q_VETO_BOTTOM50_STRESS`: aggressive stress variant; useful for sensitivity,
  not a promotion candidate by itself.
- `Q_SOFT_WEIGHT_70_130`: keep ordering, but tilt order sizing from 0.70x to
  1.30x by quality.

## Interpretation Rules

This AB should be judged on whether quality helps concentration without breaking
trend capture:

- CAGR, MaxDD, Calmar and Sharpe versus B0;
- trade count, turnover and churn;
- missed large winners after quality intervention;
- loss TOP30 reduction;
- whether improvement comes from fewer low-quality fills rather than hidden
  timing or universe changes.

## Risks

- Hard veto can miss rare low-quality trend winners.
- Quality table coverage is incomplete, especially for newer/recent symbols.
- Existing runtime path is named `moneyflow_overlay`; reports must state that it
  is being reused as a generic factor insertion path in research only.
