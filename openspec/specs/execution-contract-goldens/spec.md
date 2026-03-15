# execution-contract-goldens Specification

## Purpose
Synced from delta spec during archive. The capability contract is now part of the main spec set.

## Requirements

### Requirement: 执行链必须通过显式 contract 交接核心状态
系统 MUST 使用显式 `RuntimePlan`、`ExecutionIntent` 和 `AccountingSnapshot` 契约在执行链关键阶段交接核心状态。`order_planning`、`fill_accounting` 和 `daily_accounting` SHALL NOT 再通过隐式 dict 字段传递核心状态。

#### Scenario: 信号进入订单规划
- **WHEN** 执行链从信号阶段进入订单规划
- **THEN** 系统 MUST 使用 `ExecutionIntent` 交接买卖候选、风险标记和排序载荷
- **THEN** 下游 SHALL NOT 依赖未声明的隐式字段

#### Scenario: 成交后进入日终记账
- **WHEN** 系统完成 fill 并进入日终记账
- **THEN** 系统 MUST 使用 `AccountingSnapshot` 交接现金、持仓、filled orders、trade rows 和 counters
- **THEN** NAV、daily rows 和 metrics SHALL 从该显式快照推导

### Requirement: 主循环替换前必须有最小覆盖集 goldens
系统 MUST 在正式替换主循环前建立最小覆盖集 goldens。最小覆盖集 MUST 至少包含 `baseline_V10`、一个 locked candidate preset、一个 representative generic route 和一个 representative breakout route。

#### Scenario: golden 覆盖集准备完成
- **WHEN** 系统准备替换 strict 或 legacy 主流程
- **THEN** 每个覆盖样本 MUST 具有固定输入和可比输出
- **THEN** 覆盖项 MUST 至少包含 `orders`、`trades`、`NAV`、`perf` 和 `counters`

#### Scenario: golden 不完整时尝试替换主循环
- **WHEN** 某个覆盖样本缺少必要 golden
- **THEN** 系统 SHALL NOT 进入正式主循环替换
- **THEN** 该重构任务 MUST 先补齐 golden

### Requirement: 时间可得性审计必须覆盖敏感模块迁移
系统 MUST 对 rolling、rank、zscore、市场状态、财务和行业快照等敏感模块迁移执行单独的时间可得性审计。任何导致 10.1 价格型信号口径漂移的迁移 SHALL 被判定为失败。

#### Scenario: 迁移 rolling 或 rank 模块
- **WHEN** 系统迁移 rolling、rank 或 zscore 相关模块
- **THEN** 系统 MUST 单独验证窗口只使用历史可得样本
- **THEN** 审计结果 MUST 能说明未引入未来函数或时点错位

#### Scenario: 价格型信号结果出现偏移
- **WHEN** 迁移后 `orders`、`trades`、`NAV`、`perf` 或 `counters` 与黄金样本发生非预期偏移
- **THEN** 系统 MUST 将该迁移判定为失败
- **THEN** 不得以结构优化为理由接受该偏移


