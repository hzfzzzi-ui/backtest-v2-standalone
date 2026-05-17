## Realworld Shadow Pool Extension

This addendum extends the completed `cn_etf_research_shadow_pool_v1` work with a wider
research-only pool. The purpose is not to promote any ETF into the formal pool. The
purpose is to test a closer-to-real-world ETF opportunity set before attributing winner
or loser causes.

## Change Level

L3: ETF asset pool / tradable pool research.

## New Pool

`cn_etf_research_realworld_pool_v1`

The pool includes representative, locally refreshable ETFs across:

- Core broad beta: SSE50, SSE180, CSI300, CSI500, CSI1000, SZ100.
- Growth beta: ChiNext, ChiNext50, STAR50.
- Style beta: dividend and dividend-low-vol.
- Defensive assets: gold, 5Y treasury ETF, 10Y treasury ETF, money ETF.
- Sector/theme satellites: broker, bank, consumer, liquor, medicine, medical,
  semiconductor, chip, NEV, photovoltaic, coal, non-ferrous metals.
- Cross-border satellites: Nasdaq, S&P 500, Hang Seng, Hang Seng Tech, China Internet.

## Study Discipline

- Keep `formal_etf_pool_v1` unchanged.
- Keep signal timing, execution timing, and portfolio construction logic unchanged.
- Use `510300.SH` as the benchmark for the realworld pool study so the comparison no
  longer depends on the previous `510880.SH` benchmark choice.
- Mark all realworld pool members as research-only shadow members.
- Mark promotion gates explicitly:
  - cash / bond duration / cross-border / sector-theme / short-history symbols are
    blocked from direct formal promotion.
  - broad/style symbols remain pending validation unless their history is too short.
- Run the same three windows:
  - `2012-2017` hard gate.
  - `2016-2026` main development window.
  - `2012-2026` full audit.

## Rollback

Remove the new preset, catalog entries, study file, tests, and refreshed data rows for
symbols that are only introduced by this realworld pool. Existing formal and narrow
shadow pool behavior does not need migration.
