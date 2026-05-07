## ADDED Requirements

### Requirement: formal ETF stabilizer 在 BULL 状态下必须允许受控 partial overlay pace
当 `cn-etf-beta-sleeve` 以 formal `strategic_beta_stabilizer` 运行，且有效状态为 `BULL` 时，系统 MUST 允许 `deployment_pace` 在 `strategic_floor_cap` 之外，再吸收一部分已批准的 `tactical_overlay_cap`。该受控比例 MUST 由正式合同参数 `bull_partial_overlay_pace_ratio` 决定，且 v1 MUST 固定为 `0.5`。

系统 MUST 将 `BULL` 下的 `deployment_pace` 计算为：

`strategic_floor_cap + bull_partial_overlay_pace_ratio * tactical_overlay_cap`

系统 SHALL NOT 在 `BULL` 下继续把 `deployment_pace` 固定成仅等于 `strategic_floor_cap`。

#### Scenario: BULL pace 吸收一半 approved overlay
- **WHEN** formal ETF stabilizer 的有效状态为 `BULL`，且 `strategic_floor_cap > 0`、`tactical_overlay_cap > 0`
- **THEN** `deployment_pace` MUST 等于 `strategic_floor_cap + 0.5 * tactical_overlay_cap`
- **THEN** 系统 MUST 在正式产物中暴露 `bull_partial_overlay_pace_ratio=0.5`

#### Scenario: BULL 无 overlay 时 pace 退化到 floor
- **WHEN** formal ETF stabilizer 的有效状态为 `BULL`，但 `tactical_overlay_cap <= 0`
- **THEN** `deployment_pace` MUST 等于 `strategic_floor_cap`
- **THEN** 系统 SHALL NOT 为该日伪造 partial overlay pace

### Requirement: formal ETF stabilizer 不得借由本次 change 改写 TRANS_UP 合同
本次 `bull partial overlay pace` change MUST 仅影响 `BULL` 状态。系统 SHALL NOT 改写 `TRANS_UP` 的 `single-seat core recovery` 语义、`deployment_pace` 公式或 live target 结构。

#### Scenario: TRANS_UP 保持 single-seat core recovery
- **WHEN** formal ETF stabilizer 的有效状态为 `TRANS_UP`
- **THEN** `tactical_overlay_cap` MUST 继续保持当前 formal 合同定义
- **THEN** `deployment_pace` MUST 继续按既有 `TRANS_UP` 公式计算
- **THEN** 系统 SHALL NOT 因本次 `BULL` 变更恢复 `TRANS_UP` 的 second-seat overlay
