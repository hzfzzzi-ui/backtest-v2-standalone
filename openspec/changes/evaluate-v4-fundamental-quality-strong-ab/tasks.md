## 1. Contract

- [x] 1.1 Create OpenSpec change for stronger quality AB.
- [x] 1.2 Define proposal, design, and requirements.
- [x] 1.3 Validate OpenSpec.

## 2. Study Surface

- [x] 2.1 Add V4 stock quality strong AB study YAML.
- [x] 2.2 Dry-run Docker plan.

## 3. Main-Window Run

- [x] 3.1 Run `2016-2026` B0 and selected strong quality variants in Docker.
- [x] 3.2 Compare same-window metrics versus B0.

## 4. Reporting

- [x] 4.1 Report facts, interpretation, and decision.
- [x] 4.2 Decide whether guardrail/full windows are warranted.

## Notes

- `Q_VETO_BOTTOM50_STRESS` was not run after `Q_VETO_BOTTOM25` already failed
  on CAGR, Sharpe, MaxDD, and Calmar versus the same-window B0. Running the
  stronger stress variant is not warranted before fixing/confirming the veto
  diagnostic surface.
