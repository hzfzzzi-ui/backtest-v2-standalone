## Added Requirements

### Requirement: Desktop page shell must be owned by formal app-shell module
The desktop frontend MUST define a formal app-shell module under `frontend/assets/js/desktop-shell/` that owns page-level init and UI bridge wiring.

#### Scenario: Host bootstrap prefers formal app-shell
- **WHEN** the desktop page finishes loading
- **THEN** `desktop-shell/host.js` initializes shared state
- **AND** dispatches startup through `initDesktopAppShell()` when that function exists
- **AND** does not rely on legacy `backtest_v2.js` as the primary page initializer

### Requirement: Legacy backtest shell must not own page init
`frontend/assets/js/backtest_v2.js` MUST NOT own desktop page initialization, load-hint synchronization, or event binding once the formal app-shell module exists.

#### Scenario: Legacy shell reduced to compat layer
- **WHEN** the desktop page loads
- **THEN** page init and bridge wiring come from the formal app-shell module
- **AND** `backtest_v2.js` is limited to compat constants or other temporary legacy-only surface still not migrated
