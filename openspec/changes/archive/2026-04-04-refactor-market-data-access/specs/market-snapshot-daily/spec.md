## ADDED Requirements

### Requirement: 市场快照构建 MUST 通过统一市场数据访问层消费正式市场数据
系统 MUST 让市场快照构建通过统一市场数据访问层消费价格历史、benchmark 历史、交易日历与必要 PIT 数据。市场快照正式上 SHALL NOT 继续把直查 `pams_*`、`pit_*` 表作为长期主路径。

#### Scenario: 构建某交易日市场快照
- **WHEN** 系统为某个交易日构建市场快照
- **THEN** 构建链 MUST 通过统一市场数据访问层取得所需市场数据
- **THEN** 构建链 SHALL NOT 在正式主路径中直接依赖 `pams_ohlcv_daily` 或 `pams_ohlcv_daily_v2_runtime`

### Requirement: 市场快照接入统一访问层后 MUST 保持快照语义等价
系统在把市场快照接入统一市场数据访问层时 MUST 保持当前正式快照输出语义等价。访问边界重构 SHALL NOT 单独改变 snapshot 层字段意义、时间窗口口径或告警语义。

#### Scenario: 快照输出等价回归
- **WHEN** 系统对同一交易日执行接入前后 market snapshot 构建对照
- **THEN** 快照字段语义、告警结构与关键层级输出 MUST 保持等价
- **THEN** 任意差异 MUST 被标记为行为漂移并进入审计
