## MODIFIED Requirements

### Requirement: `v2` 升格 MUST 区分 `BJ post` 已知 provider gap 与真实 critical 构建异常

系统 MUST 将 `BJ post-2021-11-15` 的 `daily_basic.turnover_rate` 长段覆盖缺口视为已知 provider gap，而不是泛化的构建失败。

第一批 `BJ post` 已知 provider gap 仅包含：

- `issue_type = turnover_rate_imputed_zero`
- `cause_class = bj_post_daily_basic_gap`

#### Scenario: `BJ post daily_basic` provider gap 不计入 hard gate critical

- **WHEN** formal audit 识别出 `turnover_rate_imputed_zero` 且 `cause_class = bj_post_daily_basic_gap`
- **THEN** 系统 MUST 将其计入 `known_source_gap_rows`
- **THEN** 系统 SHALL NOT 将其计入 hard gate 使用的有效 `critical_exception_rows`
- **THEN** 系统 MUST 继续在异常明细和 summary 中显式暴露这批样本

#### Scenario: runtime 继续排除 `BJ post` 已知 provider gap

- **WHEN** `BJ post-2021-11-15` 的 `turnover_rate` 仍为 `imputed_zero`，且当前行没有 `daily_basic`/`float_share` 支持
- **THEN** runtime gate MUST 继续将其排除在 runtime 可消费集合之外
- **THEN** runtime gate MAY 将 traded 行单独标记为 `known_source_gap_low_turnover`
- **THEN** 系统 SHALL NOT 因这次 provider gap 归类修正而放宽 `can_consume_v10_1`
