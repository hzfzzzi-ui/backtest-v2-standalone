## ADDED Requirements

### Requirement: research_audit 必须包含 accounting_integrity gate
系统 MUST 在 `research_audit.gates` 中新增 `accounting_integrity` gate，并基于主线 execution audit 的会计恒等式证据输出统一状态。

#### Scenario: 会计恒等式出现失败
- **WHEN** execution audit 证据显示现金守恒、持仓守恒、NAV 一致性、负现金或超仓上限中任一硬性检查失败
- **THEN** `research_audit.gates.accounting_integrity.status` SHALL 为 `FAIL`

#### Scenario: 证据完整且全部通过
- **WHEN** execution audit 提供了完整的主线会计证据，且所有硬性检查均通过
- **THEN** `research_audit.gates.accounting_integrity.status` SHALL 为 `PASS`

#### Scenario: 主线证据不足
- **WHEN** 当前实验缺少足够的主线会计快照，导致系统无法证明记账自洽
- **THEN** `research_audit.gates.accounting_integrity.status` SHALL 为 `UNKNOWN`
- **THEN** 该 gate SHALL 通过 `reason` 或等价字段说明证据不足，而不是默认为 `PASS`
