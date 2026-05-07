## ADDED Requirements

### Requirement: research audit 必须显式对照 BULL partial overlay pace 的合同影响
当实验属于 formal ETF stabilizer，且启用了 `bull_partial_overlay_pace_ratio` 时，`research_audit` MUST 显式输出 `BULL` 状态下的 pace 合同摘要，用于回答 partial overlay pace 是否缩小了 `pace_policy_gap` 并提高了实际暴露。

该摘要至少 MUST 包含：
- `avg_target_exposure`
- `avg_strategic_floor_target`
- `avg_tactical_overlay_target`
- `avg_deployment_pace`
- `avg_actual_exposure`
- `avg_pace_policy_gap`
- `bull_partial_overlay_pace_ratio`
- `bull_pace_mode`

#### Scenario: BULL partial overlay pace 被审计记录
- **WHEN** formal ETF stabilizer 实验完成，且 `BULL` 状态存在有效样本
- **THEN** `audit.json` MUST 输出 `BULL` 状态下的 partial overlay pace 合同摘要
- **THEN** 该摘要 MUST 包含 `bull_partial_overlay_pace_ratio`

#### Scenario: TRANS_UP 摘要不被误记成 partial overlay pace 生效
- **WHEN** formal ETF stabilizer 实验完成，且 `TRANS_UP` 状态样本存在
- **THEN** `audit.json` MUST 继续单独输出 `TRANS_UP` 的摘要
- **THEN** 系统 SHALL NOT 把 `BULL` 的 partial overlay pace 审计字段误扩展到 `TRANS_UP`
