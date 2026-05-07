## MODIFIED Requirements

### Requirement: 主 runtime 输出状态抗抖证据
当账户层主 runtime 启用状态最短停留策略时，系统 MUST 输出能够解释 raw state 与 effective state 差异的证据字段。

#### Scenario: 主 runtime 输出 suppressed state 证据
- **GIVEN** 账户层最短停留策略抑制了一次 raw state 切换
- **WHEN** 主 runtime 生成 `run_meta`
- **THEN** 系统 MUST 输出 `suppressed_state_5`
- **AND** MUST 输出 `dwell_hold_applied = true`
- **AND** MUST 输出最短停留期配置值
