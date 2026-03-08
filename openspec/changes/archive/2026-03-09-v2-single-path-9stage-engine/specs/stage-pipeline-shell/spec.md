## ADDED Requirements

### Requirement: 单次回测必须通过唯一的 9-stage 执行壳
系统 SHALL 以单一 `stage pipeline shell` 作为后端单次回测的公开执行壳，并在每次运行中只建立一个交易日日循环。

#### Scenario: 单次运行进入 stage shell
- **WHEN** 任一正式回测请求完成 `config_json` 编译和 `DataBundle` 预加载
- **THEN** 系统 SHALL 创建一次且仅一次 stage pipeline shell 运行实例
- **THEN** 系统 SHALL 在单一交易日日循环中完成该次回测

#### Scenario: 不允许第二条公开执行路径
- **WHEN** 公开 API 或脚本触发单次回测
- **THEN** 系统 SHALL NOT 直接进入另一套并行公开编排路径

### Requirement: 9-stage 执行顺序必须固定
stage pipeline shell SHALL 在每个交易日内执行固定顺序的 stage 编排，并保持 `t` 日收盘决策、`t+1` 日开盘成交语义不变。

#### Scenario: 每日固定编排顺序
- **WHEN** 系统处理任一交易日的盘后决策阶段
- **THEN** stage 执行顺序 SHALL 为 `S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S9 -> S8 -> S7`

#### Scenario: T+1 订单调度
- **WHEN** 任一 stage 在 `t` 日盘后生成买卖信号并完成 `S7` 订单规划
- **THEN** 订单 SHALL 被挂入下一交易日的待执行队列
- **THEN** 系统 SHALL NOT 在信号日当日直接成交这些订单

### Requirement: stage 模块必须遵循统一输入输出契约
每个 stage SHALL 只消费 `DayContext`、`DataBundleView`、`PortfolioState`、`StageInputs` 和只读配置，并通过显式 `StageOutputs` 返回结果。

#### Scenario: stage 不直接查库和写盘
- **WHEN** 任一 stage 被执行
- **THEN** 该 stage SHALL NOT 直接访问数据库、provider 或实验目录写盘接口

#### Scenario: stage 输出显式化
- **WHEN** 任一 stage 完成执行
- **THEN** 该 stage SHALL 返回显式的候选、持仓、约束、计数或告警输出
- **THEN** 这些输出 SHALL 作为后续 stage 的唯一输入来源之一

### Requirement: stage 禁用时必须返回 neutral output
系统 SHALL 在 stage 被禁用时返回等价于“不过滤/不施加约束”的 neutral output，而不是切换到另一条执行路径。

#### Scenario: 关闭市场环境 stage
- **WHEN** `S2` 未启用
- **THEN** `S2` SHALL 返回不过滤市场环境的 neutral output
- **THEN** stage shell SHALL 继续沿同一条 stage 路径执行后续 stage

#### Scenario: 关闭风险约束 stage
- **WHEN** `S8` 未启用
- **THEN** `S8` SHALL 返回不额外收缩仓位或订单的 neutral output
- **THEN** 系统 SHALL NOT 因此切换到另一套 legacy 编排

### Requirement: 候选流和持仓流必须在 S7 之前合流
stage pipeline shell SHALL 在同一交易日内先分别产出候选流与持仓流结果，再由 `S7` 统一完成组合构建和订单规划。

#### Scenario: 候选流独立推进
- **WHEN** 系统执行 `S1` 到 `S6`
- **THEN** 系统 SHALL 产出仅面向新开仓候选的中间结果

#### Scenario: 持仓流独立推进
- **WHEN** 系统执行 `S9` 与 `S8`
- **THEN** 系统 SHALL 产出仅面向已有持仓退出和风险约束的中间结果

#### Scenario: S7 统一下单规划
- **WHEN** 候选流与持仓流结果均已就绪
- **THEN** `S7` SHALL 统一决定卖出、买入、现金占用和次日挂单结果
