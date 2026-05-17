## Sequential ETF Pool Expansion V2 Results

Run date: 2026-05-09

## Data Refresh

- Industry/theme v2:
  - Added 23 industry/theme symbols after realworld v1.
  - Pool size: 56 ETFs.
  - Daily refresh added 35,091 rows.
- Style/smart-beta v2:
  - Added 43 style/smart-beta symbols after industry/theme v2.
  - Pool size: 99 ETFs.
  - Catalog refresh upserted 99 rows.
  - Daily refresh added 60,722 rows and 84 dividend rows.

## Experiments

Formal control rerun:

- `1217`: `exp_20260509_040330720_5460`
- `1626`: `exp_20260509_040254706_f672`
- `1226`: `exp_20260509_040342478_ce87`

Realworld v1:

- `1217`: `exp_20260509_040048362_5718`
- `1626`: `exp_20260509_035957687_1080`
- `1226`: `exp_20260509_040113040_e983`

Industry/theme v2:

- `1217`: `exp_20260509_042512598_c21b`
- `1626`: `exp_20260509_042444711_4ddf`
- `1226`: `exp_20260509_042522973_e227`

Style/smart-beta v2:

- `1217`: `exp_20260509_044300354_47fb`
- `1626`: `exp_20260509_044216824_7939`
- `1226`: `exp_20260509_044312594_9dc4`

## Same-Code Sequential Comparison

| Window | Pool | CAGR | Sharpe | MaxDD | Trades | Turnover |
|---|---|---:|---:|---:|---:|---:|
| 2012-2017 | formal | -3.43% | -0.094 | -40.85% | 26 | 0.01288 |
| 2012-2017 | realworld v1 | 14.91% | 0.664 | -45.09% | 48 | 0.01902 |
| 2012-2017 | industry/theme v2 | 14.32% | 0.645 | -44.98% | 47 | 0.01838 |
| 2012-2017 | style/smart-beta v2 | 14.73% | 0.708 | -41.85% | 44 | 0.01527 |
| 2016-2026 | formal | 4.22% | 0.270 | -69.41% | 56 | 0.01026 |
| 2016-2026 | realworld v1 | 9.70% | 0.609 | -30.77% | 93 | 0.01942 |
| 2016-2026 | industry/theme v2 | 9.86% | 0.613 | -34.65% | 90 | 0.01881 |
| 2016-2026 | style/smart-beta v2 | 10.54% | 0.625 | -29.76% | 93 | 0.01846 |
| 2012-2026 | formal | 1.73% | 0.214 | -69.45% | 74 | 0.01251 |
| 2012-2026 | realworld v1 | 11.03% | 0.585 | -45.09% | 130 | 0.01999 |
| 2012-2026 | industry/theme v2 | 10.92% | 0.579 | -44.98% | 126 | 0.01928 |
| 2012-2026 | style/smart-beta v2 | 11.76% | 0.626 | -41.85% | 123 | 0.01751 |

## Attribution Notes

Symbol-level PnL attribution is diagnostic only; it is not a complete replacement for
the NAV curve. It is still useful for identifying which selected symbols drove the
rotation path.

Full-window style/smart-beta v2 top contributors:

- `159906.SZ` SZ Growth ETF: +643,962.
- `515030.SH` New Energy Vehicle ETF: +518,331.
- `510060.SH` Central SOE ETF: +496,860.
- `516780.SH` Rare Earth ETF: +459,469.
- `159915.SZ` ChiNext ETF: +335,602.

Full-window style/smart-beta v2 main detractors:

- `159967.SZ` ChiNext Growth ETF: -1,099,836.
- `515880.SH` Communication ETF: -1,019,544.
- `159901.SZ` SZSE 100 ETF: -335,827.
- `159845.SZ` CSI1000 ETF: -203,852.
- `510030.SH` Value ETF: -170,275.

## Conclusion

Round 1 did not prove that broader industry/theme coverage should be promoted. It
slightly improved the 2016-2026 CAGR versus realworld v1, but worsened main-window
drawdown and slightly reduced full-window CAGR.

Round 2 is the better research pool. It improves the full-window result versus both
realworld v1 and industry/theme v2, while also reducing drawdown and turnover. The
improvement is not because every style ETF is good. It comes from giving the rotation
contract a wider set of older, interpretable style alternatives, especially growth-style
and central-SOE exposures, while short-history style products remain blocked by the
promotion gate.

No symbol should be promoted directly into the formal pool from this run. The next
formal-pool discussion should be a separate `formal_etf_pool_v2` change with stricter
liquidity, overlap, history, and sleeve-role gates.
