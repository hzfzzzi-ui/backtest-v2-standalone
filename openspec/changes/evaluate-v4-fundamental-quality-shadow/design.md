## Scope

This change adds a first-pass fundamental quality layer as a shadow study only.
The study answers two questions:

1. Do we currently have PIT-safe basic quality data for the V4 stock entries?
2. If yes, can quality buckets explain later entry outcomes enough to justify a
   future AB test?

## Data Contract

Accepted data must have:

- `symbol`;
- a usable observation date, preferably `ann_date`;
- a financial period date such as `end_date`, `report_date`, or `period`;
- at least two usable quality fields from ROE/ROA/margin/cashflow/leverage.

If only `as_of` snapshot data exists, it is treated as audit context, not as a
full-cycle PIT source, unless the run explicitly marks the source as
observation-safe. The current first pass does not grant that exception.

The first importer, when used, writes Tushare `fina_indicator` rows into
`pit_stock_fundamental_quality` with `ann_date` as the observation date and
`end_date` as the financial period date.

## Factor Definition

The initial quality score is deliberately plain:

- higher ROE/ROA/margins are better;
- stronger cashflow-to-profit is better;
- lower leverage is better;
- each usable component is cross-sectionally ranked by observation date;
- the score is the average of available component percentiles.

This is not a trading rule. It is a bucket label used to inspect V4 entries.

## Output Contract

The study writes under `outputs/studies/cn_stock/v4_fundamental_quality_shadow_v1/`:

- `coverage_audit.json`;
- `entry_quality_shadow.csv` when data is usable;
- `bucket_summary.csv` when data is usable;
- `summary.md`.

When the data contract is not met, the machine output MUST say
`status = DATA_BLOCKED` and the human report MUST explain which coverage
condition failed.

## Risks

- Existing `pams_fundamental_snapshot` may look useful but is too sparse and
  lacks formal announcement-period lineage for full-cycle use.
- Tushare financial indicators can be used later, but only after importer,
  row-count, announcement-date, and restatement behavior are audited.
