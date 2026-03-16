## ADDED Requirements

### Requirement: Artifact diagnostics 必须只消费 canonical runtime diagnostics input
系统 MUST 要求 `artifacts_diagnostics.py` 及相关 diagnostics/funnel builder 只消费 canonical runtime diagnostics input，不再直接从执行本体推导最终 stage 语义。

#### Scenario: 生成 buy stage funnel
- **WHEN** 系统为实验结果生成 buy stage funnel
- **THEN** diagnostics builder MUST 通过 canonical diagnostics input 构建阶段计数和 note
- **THEN** diagnostics builder SHALL NOT 直接绑定执行层私有局部状态

#### Scenario: 生成 counters 与 reason diagnostics
- **WHEN** 系统生成 counters、reason summaries 或 surface diagnostics
- **THEN** 系统 MUST 复用同一份 canonical diagnostics input
- **THEN** 不同 artifact SHALL NOT 各自重复定义 stage count 归一化规则
