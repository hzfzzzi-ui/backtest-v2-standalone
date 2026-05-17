## Why

The stronger quality AB showed that hard quality veto and wide candidate rerank
hurt trend capture, while `Q_SOFT_WEIGHT_70_130` improved the 2016-2026 main
window. The next question is whether the improvement is robust to sizing-band
strength or only a lucky 0.70-1.30 setting.

## What Changes

- Add a research-only sizing ladder AB for V4 stock-leg fundamental quality.
- Keep trend candidates, ranking order, exits, market state, execution, costs,
  stock universe, and base V4 shell fixed.
- Vary only the quality-driven score-weighted sizing band.

## Non-Goals

- No baseline promotion.
- No hard quality veto.
- No candidate rerank.
- No ETF/combo change.
- No industry/theme factor.

## Validation

- Validate OpenSpec.
- Dry-run the study in Docker.
- Run the 2016-2026 main window first.
- Continue to 2012-2017 and 2012-2026 only if the ladder is monotonic or at
  least directionally coherent.
