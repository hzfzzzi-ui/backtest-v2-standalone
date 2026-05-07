## ADDED Requirements

### Requirement: fallback removal MUST provide a rollback path back to contract-first transitional mode
删除 unified combo legacy fallback consumption 时，系统 MUST 保留可执行的回退路径，能够把主运行入口恢复到 contract-first、legacy-fallback 的过渡模式。

#### Scenario: contract-only 删除后出现回放漂移
- **WHEN** 删除 fallback 后无法继续复现 `A_STOCK_ETF_V1` replay anchor
- **THEN** 系统 MUST 能回退到 contract-first transitional mode
- **THEN** cleanup SHALL NOT 继续推进归档或删除更多 related fallback 对象
