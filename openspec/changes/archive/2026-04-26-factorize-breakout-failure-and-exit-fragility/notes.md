## Outcome

- Added a RESEARCH_ONLY breakout failure / exit fragility surface backed by the real mainline breakout precompute context.
- Added fragility catalog, snapshot writer, fragility-score snapshot, study runner integration, and a real three-window study.
- Validation:
  - focused unit tests passed
  - openspec validate --strict passed
  - real study ran for 1217 / 1222 / 1226

## Initial research readout

- The first-cut fragility bundle does not yet produce a strong, stable high-bucket veto surface on the baseline traded-sample research universe.
- `breakout_margin_score` shows the only weakly positive veto signal in the earlier windows.
- `breakout_quality_score` behaves like a positive quality/context factor rather than a fragility veto factor.
- The equal-weight fragility score does not justify promotion; it needs a narrower second-round definition if research continues.
