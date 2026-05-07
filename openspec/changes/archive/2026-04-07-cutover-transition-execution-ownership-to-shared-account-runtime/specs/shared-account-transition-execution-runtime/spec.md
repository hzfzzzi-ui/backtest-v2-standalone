## ADDED Requirements

### Requirement: 共享账户执行 runtime 必须成为 transition execution 唯一 owner
当 `runtime_truth_source = account_allocator` 且账户层存在 `state_transition_runtime` 与 `transition_action_handoff` 时，系统 MUST 由共享账户执行 runtime 统一生成 transition execution plan、owner、status、reason code 与 reject reason。独立 sleeve SHALL NOT 再作为主执行 owner 直接给出 transition execution 结论。

#### Scenario: 账户层 runtime 接管 transition execution
- **WHEN** runtime 以账户层为主真相运行
- **AND** 当前存在有效的 transition family 与 handoff 合同
- **THEN** 系统 MUST 生成共享账户执行 runtime 的 transition execution 结论
- **THEN** 该结论 MUST 成为 run_meta、audit、query 与前端的主执行真相

### Requirement: 共享账户执行合同必须覆盖全部 transition family
系统 MUST 在合同层覆盖 `risk_on -> risk_on`、`risk_on -> defensive`、`defensive -> defensive`、`defensive -> recovery` 四类 transition family。即使某一轮只优先实现其中一类 family，未实现 family 也 MUST 由账户层显式输出 implementation status，而不是静默回落到旧独立 sleeve 语义。

#### Scenario: 未实现 family 仍由账户层显式声明状态
- **WHEN** 某个 transition family 尚未进入 execution-ready 实现
- **THEN** 账户层 MUST 输出该 family 的 implementation status
- **THEN** 系统 SHALL NOT 静默把该 family 的主执行 owner 回落为旧 ETF weak-state 路径
