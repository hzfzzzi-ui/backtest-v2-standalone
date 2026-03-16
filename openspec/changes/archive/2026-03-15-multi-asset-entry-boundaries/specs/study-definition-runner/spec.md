## ADDED Requirements

### Requirement: study 定义必须显式声明 asset scope
系统 MUST 要求正式 `.study.yaml` 定义声明 canonical `asset_scope`。`study_run` SHALL 透传该字段进入 runtime compile，而 SHALL NOT 继续通过 baseline 或脚本命名推断资产类型。

#### Scenario: 创建新的 study
- **WHEN** 用户或 AI 创建新的正式 study
- **THEN** study 定义 MUST 包含 `asset_scope`
- **THEN** 缺失该字段的 study SHALL NOT 进入正式执行

#### Scenario: generated thin script 运行 study
- **WHEN** generated thin script 调用 `study_run`
- **THEN** thin script MUST 只透传 study 中声明的 asset scope
- **THEN** thin script SHALL NOT 自行注入 A 股默认

### Requirement: baseline 绑定不得代替资产入口声明
系统 SHALL NOT 继续把 `baseline_id` 当作正式资产入口语义。baseline 只用于对照和回归，不得代替 study 的资产范围声明。

#### Scenario: study 绑定 baseline_V10.1
- **WHEN** 某个 study 以 `baseline_V10.1` 作为对照
- **THEN** 该 study 仍 MUST 自己声明 `asset_scope`
- **THEN** 系统 SHALL NOT 仅因为 baseline 属于 A 股就省略资产入口声明
