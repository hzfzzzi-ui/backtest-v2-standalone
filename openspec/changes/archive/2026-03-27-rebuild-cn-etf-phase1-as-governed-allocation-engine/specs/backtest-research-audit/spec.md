## ADDED Requirements

### Requirement: research_audit 必须显式审计 ETF Phase 1 的预算承接与三桶分配
当实验属于 ETF Phase 1 正式主线时，`research_audit` MUST 显式引用 ETF 配置引擎的预算承接与三桶分配证据，而不是继续只围绕筛票、候选与选中链路做解释。

#### Scenario: audit 能回答 ETF 预算去了哪里
- **WHEN** 用户查看 ETF Phase 1 正式主线实验的 `research_audit`
- **THEN** 审计结果 MUST 能回答 `requested_budget`、`applied_budget`、`equity_core_bucket`、`defense_tilt_bucket` 与 `cash_buffer_bucket`
- **THEN** 审计结果 MUST 为每个桶提供原因码或等价解释证据

### Requirement: research_audit 必须区分 Governor 边界和 ETF 本地配置责任
当 ETF Phase 1 未满配或发生防守倾向切换时，`research_audit` MUST 区分这是 Governor 边界导致，还是 ETF 本地配置引擎导致。

#### Scenario: audit 区分预算边界与本地分配
- **WHEN** ETF Phase 1 的 `applied_budget` 低于 `requested_budget`
- **THEN** 审计 MUST 显式区分 Governor 下发限制与 ETF 本地未部署原因
- **THEN** 审计 SHALL NOT 把所有未部署统一笼统归因为“无票可买”
