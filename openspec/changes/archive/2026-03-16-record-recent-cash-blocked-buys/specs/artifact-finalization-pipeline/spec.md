# artifact-finalization-pipeline Specification

## MODIFIED Requirements

### Requirement: Artifact diagnostics 必须输出最近一周资金不足拦截买入明细
系统 MUST 在实验 finalize pipeline 中生成 `cash_blocked_buys_recent.csv`，用于记录最近一周交易日内因资金不足被拦截的买入候选明细。该 artifact SHALL 只从明确的现金不足拒绝事件构建，而 SHALL NOT 混入一般性未入选候选。

#### Scenario: 最近一周存在资金不足拦截
- **WHEN** 实验目录中的候选审计包含 `SKIP_NO_CASH` 事件
- **THEN** 系统 MUST 输出 `cash_blocked_buys_recent.csv`
- **THEN** 该文件 MUST 至少包含 `date`、`symbol`、`cash_available`、`estimated_qty`、`estimated_amount`
- **THEN** 该文件 MUST 只保留最近 5 个交易日范围内的记录

#### Scenario: 最近一周没有资金不足拦截
- **WHEN** 候选审计中不存在最近 5 个交易日的 `SKIP_NO_CASH` 事件
- **THEN** 系统 MUST 仍输出 `cash_blocked_buys_recent.csv`
- **THEN** 该文件 SHALL 为空表，但表头 MUST 稳定存在

#### Scenario: cash-aware 规划未选中但不属于明确现金不足
- **WHEN** 候选仅因 `NOT_SELECTED_CASH_AWARE` 等原因未入选
- **THEN** 系统 SHALL NOT 将这些候选写入 `cash_blocked_buys_recent.csv`

