## Why

The Q0/Q1 audit showed that PIT fundamental quality has clear explanatory power:
high-quality buckets have better median/win-rate profile and are almost absent
from the loss TOP30. The first ranking-overlay AB was intentionally conservative,
so it may understate the practical value of the factor.

## What Changes

- Add a research-only stronger AB for V4 stock leg quality assistance.
- Reuse the PIT-safe daily quality snapshot already audited from
  `pit_stock_fundamental_quality`.
- Keep stock universe, entry signals, exits, market state, execution timing,
  costs, and base V4 shell fixed.
- Test stronger but still attributable insertion modes:
  - wider top-band quality rerank;
  - bottom-quality candidate veto stress tests;
  - quality-driven soft sizing.

## Non-Goals

- No baseline promotion.
- No quality-only entry signal.
- No ETF or combo change.
- No industry/theme factor.
- No permanent default runtime change.

## Validation

- Validate OpenSpec.
- Dry-run the study in Docker.
- Run `2016-2026` main window first.
- Continue to `2012-2017` and `2012-2026` only if the main-window result is
  interpretable and not obviously harmful.
