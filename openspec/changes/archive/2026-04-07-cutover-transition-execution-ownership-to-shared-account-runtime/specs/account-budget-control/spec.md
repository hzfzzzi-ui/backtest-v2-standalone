## MODIFIED Requirements

### Requirement: 账户层必须成为 stock / ETF 预算来源

系统 SHALL 由账户层统一给出 stock / ETF 的预算分配，并同步输出 transition handoff 合同供共享执行 runtime 消费。stock 与 ETF 运行路径 MUST 把账户层 handoff 视为正式执行输入，而不是局部参考信息。

#### Scenario: 生成组合预算
- **WHEN** runtime 进入组合预算与状态切换阶段
- **THEN** 账户层生成 stock / ETF budgets 以及 transition handoff 合同
- **THEN** stock 与 ETF 运行路径 MUST 消费该预算与 handoff，而不是各自发明 transition execution owner
