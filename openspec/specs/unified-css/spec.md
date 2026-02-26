# Capability: unified-css

## Purpose

Unify the frontend CSS into a single stylesheet (`workbench.css`) with a consistent token namespace, eliminating the dual-file system and ensuring all existing class names and JS variable references are preserved. <!-- TBD: expand -->

## Requirements

### Requirement: Single CSS file replaces dual system
The system SHALL use a single `frontend/assets/css/workbench.css` file as the only stylesheet. The files `style.css` and `backtest_v2.css` SHALL be deleted.

#### Scenario: HTML loads single stylesheet
- **WHEN** `frontend/index.html` is loaded in the browser
- **THEN** it SHALL reference exactly one CSS file: `assets/css/workbench.css`
- **THEN** there SHALL be no reference to `style.css` or `backtest_v2.css`

### Requirement: Unified token namespace
All CSS custom properties SHALL use the `--wb-*` prefix exclusively. No `--bg`, `--accent`, `--good`, `--bad`, `--warn`, `--info`, `--line`, `--text`, `--card` unprefixed tokens SHALL exist.

#### Scenario: No unprefixed tokens in workbench.css
- **WHEN** workbench.css is inspected
- **THEN** all custom property definitions in `:root` SHALL use `--wb-*` prefix
- **THEN** zero occurrences of `--bg:`, `--accent:`, `--good:`, `--bad:` (unprefixed) SHALL exist as property definitions

### Requirement: Zero override blocks
The merged CSS SHALL contain no rules whose sole purpose is undoing another rule in the same file (e.g., `transform: none` to undo a hover animation, `text-transform: none` to undo uppercase).

#### Scenario: No undo patterns
- **WHEN** workbench.css is inspected
- **THEN** there SHALL be no `.wb-app table`, `.wb-app .pill`, `.wb-app .card` override selectors
- **THEN** base component rules SHALL be written correctly the first time without needing correction

### Requirement: All existing CSS class names preserved
All CSS class names currently used in `index.html` and `backtest_v2.js` SHALL continue to be styled. No class name SHALL be renamed or removed.

#### Scenario: HTML classes all have matching CSS rules
- **WHEN** all class names in `index.html` are extracted
- **THEN** each class SHALL have at least one matching CSS rule in `workbench.css`

#### Scenario: JS dynamic classes all have matching CSS rules
- **WHEN** JS adds classes dynamically (e.g., `.active`, `.wb-ok`, `.wb-danger`, `.up`, `.down`)
- **THEN** each dynamically-applied class SHALL have a matching CSS rule in `workbench.css`

### Requirement: Unified design tokens
The design token values SHALL be unified as defined in the design document.

#### Scenario: Single color palette
- **WHEN** workbench.css token section is inspected
- **THEN** background SHALL be `#0f131a`
- **THEN** accent SHALL be `#52a8ff`
- **THEN** green SHALL be `#56c585`
- **THEN** red SHALL be `#ff6d75`
- **THEN** yellow SHALL be `#efba56`

### Requirement: No unused component styles
The merged file SHALL NOT contain styles for components not present in `index.html`.

#### Scenario: PAMS-only components removed
- **WHEN** workbench.css is inspected
- **THEN** there SHALL be no rules for `.statusbar`, `.nav`, `.fxCard`, `.cashflowList`, `.analysisList`, `.alertStrip`, `.month-selector`, `.funnel`, `.candidate-row`, `.trail`, `.detail-grid`, `.flow-guide`, `.event-row`, `.align-row`, `.gauge-bar`

### Requirement: Consistent border-radius system
The file SHALL use a 3-tier border-radius system: small (6px), medium (10px), large (14px).

#### Scenario: Radius tokens defined
- **WHEN** workbench.css `:root` is inspected
- **THEN** `--wb-radius-xs` or equivalent SHALL be 6px
- **THEN** `--wb-radius-sm` SHALL be 10px
- **THEN** `--wb-radius` SHALL be 14px

### Requirement: JS references to CSS variables preserved
All CSS variable names referenced in `backtest_v2.js` via `var(--wb-*)` or `getComputedStyle` SHALL remain defined in workbench.css.

#### Scenario: JS variable references resolve
- **WHEN** JS reads a CSS variable via `getComputedStyle` or uses `var(--wb-*)` in inline styles
- **THEN** the variable SHALL be defined in workbench.css `:root`
