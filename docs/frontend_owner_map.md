# Frontend Owner Map

This document freezes the desktop frontend ownership split for the
`close-p0-p1-architecture-gaps` change.

## Formal Owners

- `legacy shell owner`
  - Files:
    - `frontend/assets/js/backtest_v2.js`
    - `frontend/assets/js/ui-controls.js`
    - `frontend/assets/js/artifacts.js`
  - Role:
    - bootstrap page state
    - wire lightweight controls
    - publish snapshots into the bridge
  - Must not own:
    - config draft compile or validate truth
    - visible DOM under `#wbResultsWorkbenchMount`

- `config draft core owner`
  - File:
    - `frontend/assets/js/state/config-draft-core.js`
  - Role:
    - compile desktop config draft
    - validate desktop config draft
  - Must remain the single owner of config compile/validate truth

- `page shell bridge owner`
  - Files:
    - `frontend/assets/js/results-workbench-bridge.js`
    - `frontend/assets/js/pages/desktop-research-page.js`
  - Role:
    - bridge shell state into Vue
    - fetch canonical experiment surface and lazy sections
    - merge surface payloads into workbench snapshots

- `Vue results workbench owner`
  - Files:
    - `frontend/app/results-workbench/main.js`
    - `frontend/app/results-workbench/App.vue`
  - Role:
    - mount Vue into `#wbResultsWorkbenchMount`
    - own visible results workbench DOM after mount

## Frozen Boundary Rules

- `backtest_v2.js`, `ui-controls.js`, and `artifacts.js` are transitional
  shell files. They may bootstrap, bridge, or coordinate controls, but they
  must not reclaim config compile logic or become the visible owner of the
  Vue results mount.
- `config-draft-core.js` is the only formal owner for
  `buildConfigDraftCore()` and `validateConfigDraftCore()`.
- `main.js` is the only formal mount owner for `#wbResultsWorkbenchMount`.
- Any future host move must update both this document and the matching
  boundary tests in `tests/unit/test_frontend_owner_boundaries.py`.

## Local Verification

- `pytest -q tests/unit/test_frontend_owner_boundaries.py`
- `pytest -q tests/unit/test_frontend_runtime_boundaries.py`
