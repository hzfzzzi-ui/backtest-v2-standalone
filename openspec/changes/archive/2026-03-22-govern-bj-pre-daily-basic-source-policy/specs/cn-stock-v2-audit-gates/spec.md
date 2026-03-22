## MODIFIED Requirements

### Requirement: `v2` 升格 MUST 区分已知源断层与真实 critical 构建异常

系统 MUST 在 `V2` formal audit 的 canonical gate 中，显式区分：

- 真实 hard gate critical 异常
- 已确认但当前没有正式免费补源的已知源断层

第一批已知源断层仅包含：

- `issue_type = turnover_rate_imputed_zero`
- `cause_class = bj_pre_daily_basic_gap`

#### Scenario: `BJ pre daily_basic` 已知源断层不计入 hard gate critical

- **WHEN** formal audit 在 `BJ pre-2021-11-15` 识别出 `turnover_rate_imputed_zero + bj_pre_daily_basic_gap`
- **THEN** 系统 MUST 将其计入 `known_source_gap_rows`
- **THEN** 系统 SHALL NOT 将其计入 hard gate 使用的 `critical_exception_rows`
- **THEN** 系统 MUST 继续在异常明细和汇总里显式暴露这批样本

#### Scenario: canonical gate 同时输出 raw critical 与有效 critical

- **WHEN** 系统生成 formal audit summary
- **THEN** canonical gate MUST 输出 `critical_exception_rows_raw`
- **THEN** canonical gate MUST 输出 `known_source_gap_rows`
- **THEN** canonical gate MUST 输出剔除已知源断层后的 `critical_exception_rows`

#### Scenario: runtime 继续排除已知源断层低置信 turnover

- **WHEN** `BJ pre-2021-11-15` 的 `turnover_rate` 仍为 `imputed_zero` 且 `turnover_rate_confidence < 1`
- **THEN** runtime gate MUST 继续将其排除在 runtime 可消费集合之外
- **THEN** runtime gate MUST 将其单独标记为 `known_source_gap_low_turnover`
- **THEN** 系统 SHALL NOT 仅因这次审计语义修正而放宽 `can_consume_v10_1`
