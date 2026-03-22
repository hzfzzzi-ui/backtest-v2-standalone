# runtime-diagnostic-accounting Specification

## Purpose
TBD - created by archiving change decouple-runtime-diagnostics-from-execution. Update Purpose after archive.
## Requirements
### Requirement: Runtime diagnostics 必须通过独立 snapshot contract 传递
系统 MUST 定义独立的 runtime diagnostics snapshot / input contract，用于承接执行层产生的原始诊断输入，并作为 artifact diagnostics 与 surface counters 的唯一输入边界。

#### Scenario: 执行层产生日级诊断输入
- **WHEN** 执行层完成某个交易日的持仓、订单和信号处理
- **THEN** 系统 MUST 产出独立的 runtime diagnostics input，而不是直接在执行函数中定义最终 funnel 口径
- **THEN** 该 input MUST 包含 stage 计数归一化所需的原始事件字段

#### Scenario: artifact diagnostics 消费执行诊断
- **WHEN** diagnostics builder 生成 buy funnel、reason counters 或 surface diagnostics
- **THEN** 系统 MUST 只消费 runtime diagnostics snapshot / input
- **THEN** diagnostics builder SHALL NOT 直接依赖执行循环内部的隐式局部变量

### Requirement: Stage count 归一化必须属于 diagnostics 层
系统 MUST 将 `buy_candidate_count`、`after_held_filter_count`、`after_slot_filter_count`、`after_cash_lot_count` 等最终 stage 计数语义定义在 diagnostics 层，而不是执行层。

#### Scenario: route 专属 stage 计数归一化
- **WHEN** breakout route 或其他 route 需要对原始计数做口径归一化
- **THEN** 系统 MUST 在 diagnostics builder 中完成归一化
- **THEN** 执行层 SHALL NOT 直接写入最终 UI 或 artifact stage 语义

#### Scenario: baseline funnel 对照
- **WHEN** 系统对 `baseline_V10.1` 对应实验执行 diagnostics compare
- **THEN** 归一化后的 stage count MUST 与既有 baseline 结果一致
- **THEN** 任一差异都 MUST 被视为 diagnostics 口径漂移

