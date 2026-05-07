## Outcome

- Added a RESEARCH_ONLY final score composition surface backed by the real mainline breakout precompute context.
- Added final score component catalog, snapshot writer, factor-score snapshot, study runner integration, and a real three-window study.
- Validation:
  - focused unit tests passed
  - openspec validate --strict passed
  - real study ran for 1217 / 1222 / 1226

## Initial research readout

- `final_score` itself is not a positive standalone cross-sectional rank surface on the baseline traded-sample research universe.
- `volume_price_quality_score` and `breakout_quality_score` show the cleanest positive direction among atomic components.
- `conditional_tiebreak_score` and `conditional_institution_proxy_score` are the most consistently negative components across the three windows.
- The equal-weight component score remains negative, which means the current mainline composition still should not be interpreted as a simple additive alpha factor basket.
