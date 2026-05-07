## Added Requirements

### Requirement: Frontend module split must isolate desktop page shell logic
Desktop page shell logic MUST live in dedicated `desktop-shell/*` modules rather than the legacy `backtest_v2.js` shell.

#### Scenario: Page shell helpers are exported from formal module
- **WHEN** the desktop frontend needs `syncLoadHint`, `experimentLoadSummary`, `normalizeLoadItems`, `renderRightInspector`, or the page initializer
- **THEN** those helpers are provided by a formal `desktop-shell/app-shell.js` module
- **AND** downstream modules consume that module-owned surface instead of implementations defined in `backtest_v2.js`
