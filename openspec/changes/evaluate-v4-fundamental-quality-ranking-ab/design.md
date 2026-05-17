## Primary Variable

PIT fundamental quality is inserted only as a ranking overlay for same-day stock
candidate competition.

## Data Source

The factor source is `pit_stock_fundamental_quality`, imported from Tushare
`fina_indicator`:

- `ann_date` is the observation date;
- `end_date` is the financial period;
- fields are ROE, ROA, gross margin, net margin, and debt-to-assets.

The daily snapshot is built by taking, for every trade date and symbol, the
latest fundamental row with `ann_date <= trade_date`. Rows without a PIT-safe
observation date are unavailable.

## Variants

- `B0_V4_STOCK_REPLAY`: same V4 stock baseline replay.
- `Q_RANK_TIEBREAK`: quality only breaks ties after the original final score.
- `Q_BAND_RERANK_5`: quality can rerank only the top 5 same-day candidates.
- `Q_BAND_RERANK_10`: quality can rerank only the top 10 same-day candidates.

The first AB deliberately avoids a hard low-quality veto, because the shadow
showed q1 still contains occasional large winners.

## Expected Interpretation

Success does not require higher win rate alone. The relevant checks are:

- CAGR and Calmar versus B0;
- MaxDD and loss-tail behavior;
- turnover/churn;
- whether top winners are missed;
- whether the improvement, if any, comes from fewer low-quality fills rather
  than a hidden timing change.

## Risk

The existing runtime names this insertion path `moneyflow_overlay`; using it for
quality is acceptable only as a research-only reuse of the generic
`daily_factor_snapshot` contract. Reports must call this out explicitly.
