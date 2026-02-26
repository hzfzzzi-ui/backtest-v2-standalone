## ADDED Requirements

### Requirement: Risk Gate configuration UI
A new "Risk Gate" accordion block SHALL appear below Position & Risk in the Risk module, allowing configuration of portfolio-level drawdown risk control.

#### Scenario: Risk Gate UI elements
- **WHEN** the user opens the Risk module in the Drawer
- **THEN** a "Risk Gate (即将支持)" accordion SHALL be visible with controls:
  - Enable checkbox (default: unchecked)
  - Drawdown threshold input (default: -10, unit: %)
  - Action select (options: 降档 / 停手)
  - Cooldown days input (default: 5)
  - Trigger count display (placeholder "—", populated after run)

#### Scenario: Config serialized to JSON
- **WHEN** `buildConfigDraft()` is called
- **THEN** the config object SHALL include a `risk_gate` field:
  ```json
  { "enabled": false, "drawdown_threshold": -0.10, "action": "reduce", "cooldown_days": 5 }
  ```

#### Scenario: Config loaded from saved preset
- **WHEN** a saved config containing `risk_gate` is loaded
- **THEN** the Risk Gate controls SHALL be hydrated with the saved values
