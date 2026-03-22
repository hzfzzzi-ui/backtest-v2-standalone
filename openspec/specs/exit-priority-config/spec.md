# exit-priority-config Specification

## Purpose

定义退出优先级配置在前端与序列化层的展示和保存要求，确保多退出条件的评估顺序可解释且可配置。

## Requirements

### Requirement: Exit priority configuration UI
The Exit accordion block SHALL include a priority list showing the order in which exit conditions are evaluated when multiple trigger on the same day.

#### Scenario: Default priority order
- **WHEN** the page loads with default config
- **THEN** the priority list SHALL show: stop_loss > reversal > time > trail

#### Scenario: Config serialized to JSON
- **WHEN** `buildConfigDraft()` is called
- **THEN** the config object SHALL include an `exit_priority` array field, e.g. `["stop_loss", "reversal", "time", "trail"]`

#### Scenario: Config loaded from saved preset
- **WHEN** a saved config containing `exit_priority` is loaded
- **THEN** the priority list SHALL reflect the saved order

#### Scenario: Placeholder label
- **WHEN** the user views the exit priority section
- **THEN** a "(即将支持)" badge SHALL indicate this feature is not yet enforced by the engine
