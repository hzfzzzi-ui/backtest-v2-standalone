## Sequential ETF Pool Expansion V2

Run date: 2026-05-09

## Change Level

L3: ETF asset pool / tradable pool research.

## Discipline

- Keep `formal_etf_pool_v1` unchanged.
- Keep signal timing, execution timing, account budget, and portfolio construction unchanged.
- Treat both new pools as research-only shadow pools.
- Compare sequentially so attribution is not mixed:
  - Round 1: `cn_etf_research_industry_theme_pool_v2` after realworld v1.
  - Round 2: `cn_etf_research_style_smart_beta_pool_v2` after industry/theme v2.
- Use the same three windows:
  - `2012-2017` hard gate.
  - `2016-2026` main development window.
  - `2012-2026` full audit.

## Round 1: Industry / Theme Completion

Add broader industry/theme representatives for AI, robotics, computer/software/cloud,
communication/media/game, defense, battery/power, real estate/infrastructure,
chemical/steel/rare earth, breeding/energy/carbon/environmental, appliance/electronics,
and consumer electronics.

Promotion gate: all added industry/theme symbols remain blocked from direct formal
promotion by `sector_theme_semantics`.

## Round 2: Style / Smart Beta Completion

Add style and smart-beta representatives for:

- Dividend and dividend-low-vol.
- Low-volatility.
- Dividend quality, quality, and quality growth.
- Cashflow and free-cashflow.
- Value across broad, SZ, ChiNext, CSI500, HS300, and CSI1000 variants.
- CSI A500 and A500 dividend variants.
- Central/state-owned enterprise and central-SOE dividend variants.
- Enhanced index ETFs.
- Equal-weight.
- Growth-style variants.

Promotion gate: short-history style candidates are blocked by `short_history`; older
style candidates remain `pending_shadow_validation`. Industry/theme, cash, duration,
and cross-border semantic blockers remain unchanged.

## Rollback

Remove the two v2 presets, their catalog entries, study files, tests, and refreshed
data rows for symbols introduced only by these research pools. No formal baseline or
formal ETF pool migration is required.
