## 1. Extract remaining page-level init and bridge logic from `backtest_v2.js`
- [x] Add formal `desktop-shell/app-shell.js`
- [x] Move page init, navigation, load hint, bootstrap source, and UI event binding into the formal module
- [x] Update host bootstrap to prefer the formal app-shell initializer
- [x] Reduce `backtest_v2.js` to compat constants only
- [x] Align frontend harness script loading with the new app-shell module

## 2. Validate cutover
- [x] Run frontend harness validation
- [x] Run a real page startup validation
