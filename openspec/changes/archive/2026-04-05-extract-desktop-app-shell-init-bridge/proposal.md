## Why

`backtest_v2.js` no longer needs to own page-level desktop app initialization and UI bridge wiring. After host-owner cutover and runtime-surface extraction, the remaining page shell logic should move into a formal `desktop-shell/*` module so the legacy shell can shrink to compat constants only.

## What Changes

- add a formal desktop app-shell module for page init, navigation, load-hint, and UI event binding
- update host bootstrap to prefer the formal app-shell initializer
- reduce `frontend/assets/js/backtest_v2.js` to compat constants only
- align frontend harness with the new app-shell module

## Impact

- frontend desktop startup owner boundary becomes clearer
- legacy shell exits page init and bridge ownership
- current UI/runtime behavior should stay unchanged
