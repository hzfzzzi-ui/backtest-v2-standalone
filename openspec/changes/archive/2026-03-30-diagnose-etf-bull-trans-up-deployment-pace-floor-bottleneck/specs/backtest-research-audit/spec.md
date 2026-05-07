## ADDED Requirements

### Requirement: research audit 必须独立归因 BULL 与 TRANS_UP 的 deployment pace 瓶颈

当 Governed A 股主线包含 formal ETF stabilizer 时，`research_audit` MUST 分别输出 `BULL` 与 `TRANS_UP` 的 `deployment_pace` 归因结论。审计 SHALL NOT 再把两种状态混成单一的 ETF underdeployment 结论。

#### Scenario: BULL 与 TRANS_UP 独立给出结论

- **WHEN** 实验完成并生成 `research_audit`
- **THEN** 审计 MUST 分别提供 `BULL` 与 `TRANS_UP` 的 target、pace、actual 与 gap attribution 摘要
- **THEN** 审计 SHALL NOT 仅提供一个合并后的 ETF 部署缺口数字

### Requirement: research audit 必须区分 policy gap、timing gap 与 execution residual

当正式 ETF stabilizer 在 `BULL` 或 `TRANS_UP` 下出现 `approved target` 与 `actual exposure` 不一致时，`research_audit` MUST 将缺口归因为 `pace_policy_gap`、`rebalance_timing_gap` 或 `execution_residual_gap`。审计 SHALL NOT 在没有归因 owner 的情况下把总缺口直接标记为“漏部署”。

#### Scenario: policy gap 归因为合同主动保守

- **WHEN** 审计证据显示 `deployment pace` 小于 `approved target`
- **THEN** `research_audit` MUST 将该差值归因为 `pace_policy_gap`
- **THEN** 审计 SHALL NOT 将这部分差值标记为执行层缺陷

#### Scenario: timing gap 归因为月频等待

- **WHEN** 审计证据显示 `deployment pace` 为正，但 `execution_path` 或等价 reason code 表示仍在等待月频 rebalance
- **THEN** `research_audit` MUST 将该差值归因为 `rebalance_timing_gap`
- **THEN** 审计 MUST 引用对应的 execution path 证据，而不是仅凭状态名称推断

#### Scenario: residual gap 归因为执行残差

- **WHEN** 审计证据显示 policy 与 timing 均不足以解释全部差值
- **THEN** `research_audit` MUST 将剩余差值归因为 `execution_residual_gap`
- **THEN** 审计 MUST 引用订单、持仓或 accounting 证据说明该残差仍未解释完毕
