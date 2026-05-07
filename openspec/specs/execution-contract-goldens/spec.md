# execution-contract-goldens Specification

## Purpose
定义执行链 golden 覆盖集在当前正式共享执行边界下必须保护的合同语义。

## Requirements

### Requirement: 执行链必须通过当前正式合同交接核心状态
系统 MUST 使用显式 `RuntimePlan`、`action_intent_v1`、`target_book_v1`、`execution_audit_v1` 和 `AccountingSnapshot` 在执行链关键阶段交接核心状态。`order_planning`、`fill_accounting` 和 `daily_accounting` SHALL NOT 再通过旧 `ExecutionIntent` 或未声明的隐式 dict 字段传递核心状态。

#### Scenario: 信号进入订单规划
- **WHEN** 执行链从信号阶段进入订单规划
- **THEN** 系统 MUST 使用 `action_intent_v1` 交接买卖动作、优先级和建议规模
- **THEN** 系统 MUST 使用 `risk_override_v1` 交接 Governor 风险覆盖
- **THEN** 下游 SHALL NOT 依赖 `ExecutionIntent`

#### Scenario: 订单规划进入正式执行边界
- **WHEN** `order_planning` 完成当日正式执行边界构建
- **THEN** 系统 MUST 产出 `subsystem_budget_v1 / action_intent_v1 / risk_override_v1 / target_book_v1 / execution_audit_v1`
- **THEN** 旧 `candidate_boundary / candidate_plan / execution_intent` 只允许作为内部或 compat 结构存在，不得作为正式黄金合同

#### Scenario: 成交后进入日终记账
- **WHEN** 系统完成 fill 并进入日终记账
- **THEN** 系统 MUST 使用 `AccountingSnapshot` 交接现金、持仓、filled orders、trade rows 和 counters
- **THEN** NAV、daily rows 和 metrics SHALL 从该显式快照推导

### Requirement: golden 覆盖集必须保护当前正式执行边界
系统 MUST 在正式共享执行边界上维护最小 golden 覆盖集。覆盖集 MUST 至少校验：
- `RuntimePlan`
- `action_intent_v1`
- `target_book_v1`
- `execution_audit_v1`
- `AccountingSnapshot`

#### Scenario: 运行代表性 golden 样本
- **WHEN** 系统运行代表性执行链 golden 样本
- **THEN** 每个样本 MUST 具有固定输入和可比输出
- **THEN** 覆盖项 MUST 至少包含 `orders`、`trades`、`NAV`、`perf`、`counters` 以及正式执行边界 payload

#### Scenario: 尝试回退到旧执行合同
- **WHEN** 某条运行链重新暴露旧 `ExecutionIntent`
- **THEN** golden 校验 MUST 失败
- **THEN** 该改动 SHALL NOT 进入正式主路径

### Requirement: baseline gate 必须区分已批准结构升级与行为漂移
系统 MUST 让 baseline regression gate 锚定当前正式基线，并区分已批准的 schema enrichment 与未批准的执行行为漂移。

#### Scenario: 仅发生已批准的结构升级
- **WHEN** 对照结果仅出现已批准的 contract enrichment 或字段扩展
- **THEN** gate MUST 通过显式 contract 规则识别并接受这些差异
- **THEN** 系统 SHALL NOT 将其误报为执行行为失败

#### Scenario: 正式执行边界发生非预期漂移
- **WHEN** `action_intent_v1`、`target_book_v1`、`execution_audit_v1` 或 `AccountingSnapshot` 的关键语义发生非预期变化
- **THEN** gate MUST 将其判定为阻塞型失败
- **THEN** 结构优化不得作为接受该漂移的理由
