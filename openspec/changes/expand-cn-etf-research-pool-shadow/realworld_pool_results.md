## Realworld Shadow Pool Results

Run date: 2026-05-09

## Data Refresh

- Catalog refresh: 33 ETF rows upserted.
- Daily refresh: 22 newly introduced ETFs refreshed.
- `pams_cn_etf_daily`: 82,331 rows, 33 symbols, min trade date `2007-01-18`,
  max trade date `2026-05-08`.

## Experiments

Realworld pool:

- `1217`: `exp_20260509_040048362_5718`
- `1626`: `exp_20260509_035957687_1080`
- `1226`: `exp_20260509_040113040_e983`

Formal control rerun:

- `1217`: `exp_20260509_040330720_5460`
- `1626`: `exp_20260509_040254706_f672`
- `1226`: `exp_20260509_040342478_ce87`

## Same-Code Comparison

| Window | Realworld CAGR | Formal CAGR | Delta | Realworld Sharpe | Formal Sharpe | Realworld MaxDD | Formal MaxDD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2012-2017 | 14.91% | -3.43% | +18.34pct | 0.664 | -0.094 | -45.09% | -40.85% |
| 2016-2026 | 9.70% | 4.22% | +5.49pct | 0.609 | 0.270 | -30.77% | -69.41% |
| 2012-2026 | 11.03% | 1.73% | +9.30pct | 0.585 | 0.214 | -45.09% | -69.45% |

## Attribution Summary

The realworld pool beats the formal control in return and Sharpe across all three
windows. In the modern and full windows, it also materially reduces drawdown. The hard
gate window is the exception on drawdown: the realworld pool has higher return but a
deeper 2015 drawdown.

Group PnL attribution for full window:

- Broad/core alternatives: +695k
- Growth alternatives: +793k
- Style/dividend: -304k
- Defensive/cash/gold/bond: roughly flat
- Sector/theme: roughly flat (+5k)
- Cross-border: +45k

Main winners in the full window:

- `515030.SH`: +495k
- `159949.SZ`: +491k
- `512400.SH`: +396k
- `510500.SH`: +378k
- `510180.SH`: +342k
- `159901.SZ`: +322k
- `159915.SZ`: +302k

Main losers:

- `512800.SH`: -652k
- `512690.SH`: -437k
- `512890.SH`: -296k
- `513050.SH`: -172k
- `512100.SH`: -143k
- `159845.SZ`: -137k

Conclusion: widening the pool helps mainly because it adds broad/growth alternatives
and a few sector cycles. It does not prove that all sector/theme or cross-border ETFs
should be promoted. Several real-world categories are useful as research opportunity
set breadth, but remain blocked from direct formal promotion by semantics or stability
gates.
