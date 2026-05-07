## ADDED Requirements

### Requirement: 个股 alpha 因子必须输出正式日频快照

系统 MUST 为个股 alpha 因子输出正式日频 `factor_snapshot`，至少包含 `date`、`symbol`、`factor_id`、`raw_value`、`normalized_value`、`rank_value`、`availability_flag` 和 `asof_timestamp`。

#### Scenario: 生成某日的个股因子快照

- **WHEN** 研究系统为某个交易日生成个股 alpha 因子快照
- **THEN** 每条快照 MUST 明确记录该日、标的和因子标识
- **THEN** 快照 MUST 同时输出原始值、标准化值和秩次值

#### Scenario: 因子依赖数据不可用

- **WHEN** 某个因子的依赖数据在当日不可用
- **THEN** 系统 MUST 通过 `availability_flag` 显式标记不可用
- **THEN** 系统 SHALL NOT 静默删除该条因子记录

### Requirement: 因子快照必须具备可审计的 as-of 语义

系统 MUST 为每条 `factor_snapshot` 记录可审计的 `asof_timestamp` 或等价 as-of 语义，以保证后续研究和 runtime 消费可以验证其时间可得性。

#### Scenario: 审计因子快照时间可得性

- **WHEN** 用户或审计流程检查某条因子快照
- **THEN** 系统 MUST 能回答该值使用了哪个时点之前可得的数据
- **THEN** 因子快照 SHALL NOT 依赖仅在未来才可知的数据
