## Primary Variable

The only variable is the quality sizing band:

- `Q_SOFT_WEIGHT_85_115`: conservative tilt.
- `Q_SOFT_WEIGHT_80_120`: medium tilt.
- `Q_SOFT_WEIGHT_70_130`: wider tilt.

The overlay does not change candidate order. It maps PIT fundamental quality to
score-weighted order sizing inside the already selected/planned candidate band.

## Data Contract

Use the audited PIT-safe snapshot:

`outputs/studies/cn_stock/v4_fundamental_quality_ranking_ab_v1/snapshots/fundamental_quality_daily_snapshot.csv`

The snapshot uses only `ann_date <= date`; missing quality stays missing and is
not converted into a high score.

## Interpretation

A viable sizing ladder should show:

- no large MaxDD deterioration versus B0;
- Calmar/Sharpe improvement that is not isolated to one exact band;
- no dramatic turnover or trade-count inflation;
- explainability: quality changes exposure size, not signal timing.

If only the widest band works and narrower bands do not, treat the result as
fragile and do not advance to promotion.
