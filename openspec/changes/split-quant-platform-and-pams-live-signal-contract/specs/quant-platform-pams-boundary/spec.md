## ADDED Requirements

### Requirement: 双系统 MUST 有唯一职责边界
量化研究平台 MUST 负责研究真值，PAMS MUST 负责资产真值。任何新增能力 SHALL 明确归属到其中一个系统，不得同时在两个系统中实现同一层级的策略计算、账户真值或交易生命周期主状态机。

#### Scenario: 新增研究能力
- **WHEN** 新增策略实验、baseline、研究数据口径或调仓包生成能力
- **THEN** 该能力 MUST 落在量化研究平台
- **THEN** PAMS SHALL NOT 复制该研究逻辑

#### Scenario: 新增资产管理能力
- **WHEN** 新增账户、持仓、现金、审批、通知或交易生命周期能力
- **THEN** 该能力 MUST 落在 PAMS
- **THEN** 量化研究平台 SHALL NOT 成为资产真值来源

### Requirement: PAMS MUST NOT 复算研究策略
PAMS MUST 只消费量化研究平台发布的正式调仓包。PAMS SHALL NOT 通过内部策略扫描、回测引擎、复制版研究代码或读取研究平台内部实验目录来生成实盘调仓建议。

#### Scenario: PAMS 展示今日调仓建议
- **WHEN** PAMS app/web 需要展示某 live 策略的今日调仓建议
- **THEN** PAMS MUST 从已接收且校验通过的调仓包读取建议
- **THEN** PAMS SHALL NOT 调用本地策略扫描或回测代码重算建议

### Requirement: 运行产物 MUST NOT 成为长期跨系统接口
`outputs/`、`outputs/mobile_ops/*`、`outputs/ops/sim_account/*` 等运行产物路径 SHALL 仅作为审计、兼容或调试镜像。跨系统正式接口 MUST 使用显式 API、数据库表或版本化消息合同。

#### Scenario: PAMS 接收研究平台输出
- **WHEN** PAMS 需要消费研究平台的 live 策略输出
- **THEN** PAMS MUST 通过版本化调仓包合同接收
- **THEN** PAMS SHALL NOT 直接读取研究平台 `outputs/` 目录作为正式输入

### Requirement: legacy 研究实现 MUST 被标记并退出主路径
PAMS 中既有策略扫描、旧回测、复制版 `backtest_V2` 和相关调度任务 MUST 被标记为 legacy。标记后新增功能 SHALL NOT 依赖这些 legacy 逻辑作为主路径。

#### Scenario: 调度器准备运行旧策略扫描
- **WHEN** PAMS 调度器命中 legacy 策略扫描任务
- **THEN** 系统 MUST 能通过配置禁用该任务
- **THEN** 禁用后 PAMS 主通知流 SHALL NOT 从 legacy 策略扫描产生实盘建议
