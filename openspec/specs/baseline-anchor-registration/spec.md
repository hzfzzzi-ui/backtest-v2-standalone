# baseline-anchor-registration Specification

## Purpose
TBD - created by archiving change add-baseline-v10-2-v2-strict-pit-2012-2016. Update Purpose after archive.
## Requirements
### Requirement: 系统必须支持登记新的正式 baseline 版本锚点
系统 MUST 支持把指定配置快照、指定 linked experiment 和指定窗口组合登记为新的正式 baseline 版本锚点。baseline 版本锚点 MUST 产出独立的 `outputs/baselines/<baseline_id>/config.json` 与 `baseline.json`，并写入 baseline 索引。

系统 MUST 支持把指定配置快照、指定 linked experiment 和指定窗口组合登记为新的正式 baseline 版本锚点。baseline 版本锚点 MUST 产出独立的 `outputs/baselines/<baseline_id>/config.json` 与 `baseline.json`，并写入 baseline 索引。

#### Scenario: 新增 baseline_V10.2
- **WHEN** 操作员以正式流程新增 `baseline_V10.2`
- **THEN** 系统 MUST 在 `outputs/baselines/baseline_V10_2/` 写入独立配置与元数据
- **THEN** 系统 MUST 将其写入 `outputs/baselines/index.json`
- **THEN** 系统 MUST 为该 baseline 记录 `linked_exp_id`### Requirement: 正式 baseline 版本锚点必须固定配置快照
系统 MUST 为每个正式 baseline 版本锚点固化当次运行的配置快照，不得在读取旧 baseline 时回看当前主线配置文件。

#### Scenario: 读取 baseline_V10.2
- **WHEN** 用户或系统读取 `baseline_V10.2`
- **THEN** 系统 MUST 读取 `outputs/baselines/baseline_V10_2/config.json`
- **THEN** 系统 SHALL NOT 通过重新解析 `baseline_V10.1` 推导 `baseline_V10.2`

### Requirement: 正式 baseline 版本锚点必须固定配置快照
系统 MUST 为每个正式 baseline 版本锚点固化当次运行的配置快照，不得在读取旧 baseline 时回看当前主线配置文件。

#### Scenario: 读取 baseline_V10.2
- **WHEN** 用户或系统读取 `baseline_V10.2`
- **THEN** 系统 MUST 读取 `outputs/baselines/baseline_V10_2/config.json`
- **THEN** 系统 SHALL NOT 通过重新解析 `baseline_V10.1` 推导 `baseline_V10.2`

