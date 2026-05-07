## MODIFIED Requirements

### Requirement: 账户层必须成为 runtime 唯一真相

系统 SHALL 将账户层预算输出与账户层状态切换执行输出一并视为 runtime 顶层真相。

#### Scenario: runtime 进入预算驱动模式
- **WHEN** runtime 编译正式运行输入
- **THEN** 顶层真相来自账户层 budgets、状态切换合同与共享执行 owner
- **THEN** sleeves 只消费账户层输出，不再定义 transition execution 主结论

### Requirement: explain 与 audit 必须统一到账户叙事

系统 SHALL 让 explain、audit、query 和 frontend 结果展示优先解释账户预算层与共享账户执行 runtime。旧 combo 叙事与 ETF 局部 weak-state 执行路径只允许进入 reference 或 diagnostics 区。

#### Scenario: 查看组合结果
- **WHEN** 用户查看 runtime explain、审计、查询结果或前端结果
- **THEN** 系统优先展示账户层 budgets、state transition runtime 与 transition execution owner
- **THEN** 旧 combo 叙事与 ETF 局部执行路径 SHALL NOT 作为同级主真相并列展示
