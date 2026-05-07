## ADDED Requirements

### Requirement: 账户层过渡态最短停留
系统 MUST 在账户层为 `TRANS_UP` 和 `TRANS_DOWN` 提供最短停留策略，以减少过渡态短期抖动。

#### Scenario: 过渡态未达到最短停留期
- **GIVEN** 前一日账户有效状态为 `TRANS_DOWN`
- **AND** 当前连续停留天数小于配置的最短停留期
- **AND** 当日 raw state 解析结果切换到其他状态
- **WHEN** 系统解析账户有效状态
- **THEN** 系统 MUST 保持 `effective_state_5 = TRANS_DOWN`
- **AND** MUST 输出 `suppressed_state_5`
- **AND** MUST 标记 `dwell_hold_applied = true`

#### Scenario: 过渡态达到最短停留期
- **GIVEN** 前一日账户有效状态为 `TRANS_UP`
- **AND** 当前连续停留天数大于等于最短停留期
- **WHEN** raw state 解析结果切换到其他状态
- **THEN** 系统 MUST 允许 `effective_state_5` 按 raw state 正常切换

### Requirement: 抗抖解释可观测
系统 MUST 在主 runtime 中输出 raw/effective state 与最短停留解释字段。

#### Scenario: 输出账户层抗抖 explain
- **WHEN** 主 runtime 生成账户层状态解释
- **THEN** MUST 输出 `raw_state_5`
- **AND** MUST 输出 `effective_state_5`
- **AND** MUST 输出 `previous_account_state_run_days`
- **AND** MUST 输出 `transient_min_dwell_days`
- **AND** MUST 输出 `dwell_hold_applied`
