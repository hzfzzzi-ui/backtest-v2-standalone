## 1. Contract

- [x] 1.1 Define the D5 3-day runtime AB scope and non-goals.
- [x] 1.2 Add a declarative study with B0 replay and D5 3-day runtime variants.

## 2. Runtime Hook

- [x] 2.1 Add optional D5 strategy/provider parameters, defaulting off.
- [x] 2.2 Emit D5 partial sell signals only at the configured post-entry bar.
- [x] 2.3 Preserve normal runtime order planning, fills, cash, positions, and NAV.

## 3. Verification

- [x] 3.1 Add unit tests proving default-off behavior and D5 sell-signal generation.
- [x] 3.2 Add a unit test proving the study keeps the same runtime source and changes only D5 settings.
- [x] 3.3 Validate the OpenSpec change in strict mode.
- [x] 3.4 Run study dry-run inside Docker.

## 4. Runtime AB

- [x] 4.1 Run the main 2016-2026 window inside Docker.
- [x] 4.2 Audit B0 vs D5 metrics, trades, NAV, D5 sell count, and re-entry/capital-reuse evidence.
- [x] 4.3 If main-window evidence is interpretable, run guardrail and full-audit windows.

## 5. Conclusion

- [x] 5.1 Record experiment ids, runtime duration, and same-window deltas.
- [x] 5.2 State whether D5 3-day runtime exit is worth keeping, changing, or rejecting.
