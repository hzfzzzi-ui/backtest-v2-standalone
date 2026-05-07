# account-allocation-runtime-cutover Specification

## Purpose

定义账户配置中枢接管 runtime 的最终切换合同，使系统正式从组合装配模式转为账户预算驱动模式。

## Requirements

### Requirement: 账户层必须成为 runtime 唯一真相

系统 SHALL 将账户层预算输出、状态切换合同与共享账户 transition execution 一并视为 runtime 顶层真相。

#### Scenario: runtime 进入账户预算驱动模式
- **WHEN** runtime 编译正式运行输入
- **THEN** 顶层真相来自账户层 budgets、状态切换合同和共享执行 owner
- **THEN** sleeves 只消费账户层输出，不再定义 transition execution 主结论

### Requirement: explain 与 audit 必须统一到账户叙事

系统 SHALL 让 explain、audit、query 和 frontend 结果展示优先解释账户预算层与共享账户执行 runtime。旧 combo 叙事与 ETF 局部 weak-state 执行路径只允许进入 reference 或 diagnostics 区。

#### Scenario: 查看组合结果
- **WHEN** 用户查看 runtime explain、审计、查询结果或前端结果
- **THEN** 系统优先展示账户层 budgets、state transition runtime 与 transition execution owner
- **THEN** 旧 combo 叙事与 ETF 局部执行路径 SHALL NOT 作为同级主真相并列展示

### Requirement: 固定组合形态必须降级为 reference

系统 SHALL 将旧的固定 `50/50` 组合作为 baseline、benchmark 或 fallback reference，而不是主 runtime 合同；当 `runtime_truth_source = account_allocator` 时，旧 combo/reference 不得与账户层主叙事并列承担解释权。

#### Scenario: 读取旧基线
- **WHEN** 系统加载历史固定组合基线
- **THEN** MAY 将其作为 reference 或 compatibility input
- **THEN** 当前 runtime 仍以账户层预算和状态切换为唯一主真相
- **THEN** query 与 frontend 只能把旧 combo 展示为 reference 区

#### Scenario: `RISK_OFF` 解释账户层预算
- **WHEN** `account_allocator_runtime.effective_state_5` 为 `RISK_OFF`
- **THEN** explain、audit 和 frontend 结果展示 SHALL 优先解释 `defense` 与 `core_beta` 的账户层预算
- **THEN** 旧 `50/50` 结构 SHALL 只作为 reference 展示，不得覆盖账户层左侧累积预算语义
