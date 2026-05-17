## ADDED Requirements

### Requirement: C1 theme health shadow MUST be research-only

The system MUST provide a `cn_stock_etf/cn_stock_etf_theme_health_shadow_v1` study that audits held theme weakening without modifying runtime behavior, NAV, baseline, stock pool, ETF pool, ranking factors, execution timing, allocation, or exits.

#### Scenario: Study result is written

- **WHEN** the C1 runner completes a window
- **THEN** the run output MUST include `research_only=true`
- **THEN** the run output MUST include `not_nav_backtest=true`
- **THEN** the run output MUST not include a runtime experiment id unless a future separate runtime AB explicitly creates one

### Requirement: C1 MUST audit source lineage

The runner MUST read from a V3 attribution bundle and audit required source files before deriving theme health labels.

#### Scenario: Required source files are present

- **WHEN** `manifest.json` and `long_daily_theme_alignment.csv` are present
- **THEN** the runner MUST write source lineage including baseline id, stock component exp id, ETF component exp id, and source artifact dir

#### Scenario: Required source files are missing

- **WHEN** any required source file is missing
- **THEN** the runner MUST mark the verdict as `inconclusive`
- **THEN** the runner MUST list missing files in the machine summary

### Requirement: C1 MUST label held theme health from proxy and candidate evidence

For each study window, the runner MUST emit held-theme daily rows with theme, date, exposure, proxy return evidence, rank evidence, candidate pressure, health score, and health label.

#### Scenario: Held theme is weak on several dimensions

- **WHEN** a held theme has at least the configured confirmed flag count on a date
- **THEN** the row MUST be labeled `confirmed_weak`

#### Scenario: Held theme has partial weakness

- **WHEN** a held theme has at least the configured watch flag count but fewer than the confirmed flag count
- **THEN** the row MUST be labeled `watch`

### Requirement: C1 MUST summarize windows and themes

The runner MUST write window summaries and theme summaries with held days, watch days, confirmed weak days, average exposure, max exposure, proxy coverage, top examples, and first/last confirmed weak date.

#### Scenario: Window summary is written

- **WHEN** the runner completes a window
- **THEN** machine outputs MUST include daily, theme summary, window summary, and summary json
- **THEN** human outputs MUST include a markdown report explaining that labels are diagnostic only

### Requirement: C1 MUST not overstate coverage

If ETF proxy coverage or source coverage is insufficient for a window, the runner MUST mark coverage risk and avoid treating the result as a baseline upgrade gate.

#### Scenario: Proxy coverage is low

- **WHEN** held-theme rows have low proxy availability
- **THEN** the verdict MUST be `inconclusive` or `partial`
- **THEN** the report MUST state that the result is suitable for diagnosis, not baseline promotion
