## MODIFIED Requirements

### Requirement: 系统必须支持重挂既有正式 baseline 版本锚点

系统 MUST 支持在不改变既有 `baseline_id` 的前提下，将正式 baseline 版本锚点重挂到新的官方窗口与新的 `linked_exp_id`。重挂 MUST 同步更新 `outputs/baselines/<baseline_id>/config.json`、`baseline.json` 与 `outputs/baselines/index.json`，并保证三者的窗口、配置哈希和 linked experiment 一致。

#### Scenario: 将 baseline_V10.1 正式锚点重挂到 2012-01-04

- **WHEN** 操作员明确批准将 `baseline_V10.1` 的官方窗口从 `2021-01-04` 改为 `2012-01-04`
- **THEN** 系统 MUST 将 `outputs/baselines/baseline_V10_1/config.json` 的 `universe.start` 更新为 `2012-01-04`
- **THEN** 系统 MUST 将 `outputs/baselines/baseline_V10_1/baseline.json` 的 `linked_exp_id` 更新为新的官方实验
- **THEN** 系统 MUST 将 `outputs/baselines/index.json` 中 `baseline_V10_1` 的 `start_year`、`linked_exp_id`、`config_hash` 与新锚点保持一致

### Requirement: 重挂后的正式 baseline 必须固定为新的官方配置快照

系统 MUST 在完成正式 baseline 锚点重挂后，将新的配置快照固化为该 baseline 的唯一官方配置来源。系统 SHALL NOT 继续通过旧窗口配置或旧 linked experiment 推导当前 baseline 真相。

#### Scenario: 读取重挂后的 baseline_V10.1

- **WHEN** 用户或系统读取已重挂的 `baseline_V10.1`
- **THEN** 系统 MUST 读取 `outputs/baselines/baseline_V10_1/config.json` 作为唯一官方配置快照
- **THEN** 系统 SHALL NOT 再把 `2021-2026` 的旧配置视为 `baseline_V10.1` 的当前官方真相
