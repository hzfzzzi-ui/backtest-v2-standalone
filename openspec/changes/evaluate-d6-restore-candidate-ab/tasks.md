## 1. Contract

- [x] 1.1 Add OpenSpec proposal/design/spec/tasks and pass strict validation.
- [x] 1.2 Add declarative combo study for B0, D5 immediate, and D5 immediate plus restore.

## 2. Implementation

- [x] 2.1 Add research-only restore candidate strategy/runtime params with default disabled behavior.
- [x] 2.2 Arm and clear restore state around partial D5 confirmation exits and restore fills.
- [x] 2.3 Allow explicit restore candidates through the provider held filter.
- [x] 2.4 Cap restore buy sizing to the delta between normal target and current holding.
- [x] 2.5 Add focused unit tests for params, restore signal emission, and delta top-up sizing.

## 3. Verification

- [x] 3.1 Validate OpenSpec in strict mode.
- [x] 3.2 Run focused unit tests.
- [x] 3.3 Run local and Docker dry-run for the study.
- [x] 3.4 Run Docker 2016-2026 main window.
- [x] 3.5 If interpretable, run Docker 2012-2017 and 2012-2026.

## 4. Reporting

- [x] 4.1 Write same-window performance and restore-count analysis.
- [x] 4.2 Update study journal and state continue/reject/hold without baseline promotion.
