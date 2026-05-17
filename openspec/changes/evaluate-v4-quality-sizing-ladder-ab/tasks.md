## 1. Contract

- [x] 1.1 Create OpenSpec change.
- [x] 1.2 Define proposal, design, and requirements.
- [x] 1.3 Validate OpenSpec.

## 2. Study Surface

- [x] 2.1 Add quality sizing ladder study YAML.
- [x] 2.2 Docker dry-run the study.

## 3. Main Window

- [x] 3.1 Run missing 2016-2026 ladder variants.
- [x] 3.2 Reuse same-window B0 and 70-130 evidence where valid.
- [x] 3.3 Summarize ladder metrics and runtime.

## 4. Decision

- [x] 4.1 Decide whether to run 2012-2017 guardrail.
- [x] 4.2 Decide whether to run 2012-2026 full audit.

## Notes

- Main window: only `Q_SOFT_WEIGHT_70_130` beat same-window B0 on CAGR,
  Sharpe, and Calmar; `85-115` failed and `80-120` was effectively flat/slightly
  weaker than B0.
- Guardrail window: `Q_SOFT_WEIGHT_70_130` improved MaxDD but lost CAGR,
  Sharpe, and Calmar versus same-window B0.
- Decision: do not run 2012-2026 full audit and do not promote. Keep quality as
  explanatory and candidate-sizing research, not accepted strategy logic.

## 5. Follow-up Wider Band

- [x] 5.1 Add `Q_SOFT_WEIGHT_50_150` aggressive sizing variant.
- [x] 5.2 Docker dry-run `Q_SOFT_WEIGHT_50_150`.
- [x] 5.3 Run `2016-2026` main window for `Q_SOFT_WEIGHT_50_150`.
- [x] 5.4 If main-window result is useful, run `2012-2017` guardrail for the
  same variant.
- [x] 5.5 Update report with the wider-band conclusion.

## Follow-up Notes

- `Q_SOFT_WEIGHT_50_150` improved 2016-2026 CAGR and Sharpe versus same-window
  B0 and `70-130`, but worsened MaxDD and Calmar versus `70-130`.
- `Q_SOFT_WEIGHT_50_150` failed 2012-2017 guardrail versus same-window B0 on
  CAGR, Sharpe, MaxDD, and Calmar.
- Decision unchanged: no 2012-2026 full audit and no promotion. Keep quality as
  explanatory/context sizing research only.
