## ADDED Requirements

### Requirement: Governor 必须为 ETF 稳定器 V2 输出独立部署语义
当 `cn_etf_beta` 以稳定器 V2 模式运行时，Governor MUST 为该 sleeve 单独输出可审计的部署语义，而不允许 ETF 继续只继承当前研究型小仓逻辑。

该部署语义至少 MUST 包含：
- `target_exposure`
- `min_deployable_exposure`
- `fallback_allowed`
- `under_deploy_reason_codes`

#### Scenario: ETF 稳定器 V2 在可部署状态下获得正式目标暴露
- **WHEN** 当前有效状态允许 ETF beta sleeve 部署
- **THEN** Governor MUST 为 `cn_etf_beta` 输出显式 `target_exposure`
- **THEN** 产物 MUST 能区分“目标暴露”与“实际暴露”

#### Scenario: ETF 稳定器 V2 被压缩时必须解释原因
- **WHEN** ETF 稳定器 V2 的实际暴露显著低于 `target_exposure`
- **THEN** Governor MUST 输出 `under_deploy_reason_codes`
- **THEN** 系统 SHALL NOT 只留下聚合后的 `TOTAL_EXPOSURE_CAP_REDUCED` 而没有 ETF sleeve 级解释

### Requirement: Governor 不得把 ETF 稳定器长期压成接近不部署而无证据
Governor MUST 避免出现 ETF 稳定器在 `RISK_ON / NEUTRAL` 长期平均接近不部署而无法解释的状态；若出现，产物 MUST 明确证明是 regime、drawdown、cooldown、exposure cap 或 fallback 约束导致。

#### Scenario: RISK_ON 下 ETF 暴露长期偏低
- **WHEN** ETF 稳定器 V2 在研究窗口内出现长期平均实际暴露显著低于目标暴露
- **THEN** Governor 证据链 MUST 指出造成偏低的主导原因
- **THEN** 研究审计 MUST 能据此判断该 V2 方案是否真实部署不足
