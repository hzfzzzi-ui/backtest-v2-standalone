## ADDED Requirements

### Requirement: ETF beta sleeve 必须显式声明目标暴露与最小可部署暴露
系统 MUST 为 `cn_etf_beta` 输出显式的 `target_exposure` 与 `min_deployable_exposure`，并把它们视为 ETF 稳定器正式部署语义的一部分。

#### Scenario: 输出 ETF 目标暴露语义
- **WHEN** 系统运行 `cn_etf_beta`
- **THEN** `run_meta`、`audit` 或日级产物 MUST 暴露 `target_exposure`
- **THEN** 同一批产物 MUST 暴露 `min_deployable_exposure`

### Requirement: ETF beta sleeve 必须显式区分理论可部署与实际已部署
系统 MUST 能区分 ETF sleeve 的理论目标暴露与实际已部署暴露，并对二者差值给出正式说明。

#### Scenario: 记录 deployability gap
- **WHEN** ETF sleeve 的实际暴露低于目标暴露
- **THEN** 系统 MUST 输出 `deployability_gap` 或等价证据
- **THEN** 系统 MUST 给出 `under_deploy_reason_codes`

### Requirement: ETF beta sleeve 的 fallback 必须视为 sleeve-local 暴露组成
系统 MUST 把 ETF fallback 视为 ETF sleeve-local 暴露组成的一部分，而不是隐式并入独立 defense sleeve。

#### Scenario: fallback 进入 ETF sleeve 暴露统计
- **WHEN** ETF sleeve 触发 fallback
- **THEN** 系统 MUST 在 ETF sleeve 的暴露统计中单独标记 fallback 暴露
- **THEN** 系统 SHALL NOT 把该 fallback 静默记作正式 defense sleeve 暴露
