## MODIFIED Requirements

### Requirement: T+1 执行验证
系统 SHALL 验证所有原始 alpha 信号、组合后信号和最终订单都遵循 T+1 执行规则（`t` 日信号形成，`t+1` 日成交）。

#### Scenario: 组合后信号次日执行
- **WHEN** 某交易日生成 `raw_alpha_signals` 与 `composed_buy_signals`
- **THEN** 基于这些信号生成的订单 SHALL 排入 `pending[next_trading_day]`
- **THEN** 系统 SHALL 不在信号日当天执行这些订单

#### Scenario: 全周期无违规
- **WHEN** 回测完成
- **THEN** `audit_summary.t1_check_fail` SHALL 为 `0`

---

### Requirement: audit.json 输出格式
`audit.json` SHALL 遵循固定 schema，便于机器解析，并在多 alpha 组合场景下扩展组合与归因字段。

#### Scenario: 顶层结构
- **WHEN** `audit.json` 生成
- **THEN** 顶层 SHALL 包含 `version`、`exp_id`、`generated_at`、`summary`、`data_quality`、`flagged_days`、`flags` 字段

#### Scenario: summary 结构
- **WHEN** `audit.json` 生成
- **THEN** `summary` SHALL 继续包含现有审计统计字段
- **THEN** `summary` SHALL 额外包含 `raw_signal_counts_by_alpha`、`composed_signal_counts_by_alpha`、`blocked_signal_counts_by_reason`、`conflict_resolution_counts`、`source_only_exit_count`、`global_risk_override_count`

#### Scenario: flagged_days 结构
- **WHEN** 某交易日的任一检查失败、发生组合冲突或出现来源感知退出
- **THEN** `flagged_days` SHALL 包含该日的完整审计记录
- **THEN** 该记录 SHALL 能表示 `raw_alpha_signals`、`composed_buy_signals`、`composed_sell_signals`、`same_symbol_conflicts`、`source_exit_count`、`global_risk_override_count`

## ADDED Requirements

### Requirement: 组合层审计输出
系统 SHALL 为多 alpha 组合输出最小可验证的审计统计，至少覆盖“组合前”“组合后”“冲突裁决后”三个层面。

#### Scenario: 原始信号与组合后信号计数
- **WHEN** 某交易日启用多 alpha 组合
- **THEN** 审计输出 SHALL 记录每个 `alpha_id` 的原始信号数量
- **THEN** 审计输出 SHALL 记录每个 `alpha_id` 的组合后放行数量

#### Scenario: 同股冲突裁决被审计
- **WHEN** 某交易日某标的发生同股冲突裁决
- **THEN** 审计输出 SHALL 记录冲突涉及的 `alpha_id`、被放行的策略和裁决原因

---

### Requirement: 来源退出审计输出
系统 SHALL 区分“来源策略退出”和“全局风险覆盖退出”，并在审计结果中分别统计。

#### Scenario: 来源策略退出被记录
- **WHEN** 某持仓因其 `entry_alpha_id` 对应的 `S9` 规则而退出
- **THEN** 审计输出 SHALL 记录该笔退出属于 `source_only`
- **THEN** 退出统计 SHALL 归入对应 `alpha_id`

#### Scenario: 全局风险覆盖退出被记录
- **WHEN** 某持仓因 `S8` 的全局风险规则而被强平
- **THEN** 审计输出 SHALL 记录该笔退出属于 `global_risk_override`
- **THEN** 该笔退出 SHALL 不计入任意来源策略的正常退出次数
