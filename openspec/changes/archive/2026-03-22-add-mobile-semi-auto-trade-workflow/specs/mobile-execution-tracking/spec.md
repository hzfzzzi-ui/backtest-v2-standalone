## ADDED Requirements

### Requirement: 手机端必须展示待执行指令的生命周期状态
系统 MUST 为每个 `approval ticket` 提供清晰的生命周期状态，至少包括 `approved_pending`、`claimed`、`submitted`、`partially_filled`、`filled`、`cancelled`、`rejected`、`expired`。手机端 SHALL 能按 ticket 查看当前状态与最近事件。

#### Scenario: 指令被执行器接单
- **WHEN** 桌面执行器领取某张待执行 ticket
- **THEN** 系统 SHALL 将其状态更新为 `claimed`
- **THEN** 手机端 SHALL 能看到领取时间与执行器标识

#### Scenario: 指令最终成交
- **WHEN** 桌面执行器回写全部成交结果
- **THEN** 系统 SHALL 将 ticket 状态更新为 `filled`
- **THEN** 手机端 SHALL 展示成交数量、成交均价和完成时间

### Requirement: 系统必须记录执行事件流而非只保留最终状态
系统 MUST 为每张 ticket 保存 append-only 的 `execution events`，用于表达状态变化、成交回写、拒单、撤单和异常说明。手机端 SHALL 可按时间顺序查看事件流。

#### Scenario: 指令被拒单
- **WHEN** 执行器回写拒单或风控拒绝事件
- **THEN** 系统 SHALL 记录拒单事件、错误码和可读说明
- **THEN** 手机端 SHALL 将 ticket 状态标记为 `rejected`

#### Scenario: 指令部分成交
- **WHEN** 执行器回写部分成交事件
- **THEN** 系统 SHALL 保留累计成交数量与剩余数量
- **THEN** 手机端 SHALL 展示部分成交状态而不是直接显示完成

### Requirement: 执行回写必须可用于复盘和持仓对账
系统 MUST 将执行结果以结构化字段回写，至少包含 ticket id、股票标识、动作类型、委托数量、成交数量、成交均价、偏差说明和回写时间。该数据 SHALL 可被每日复盘摘要与持仓对账流程复用。

#### Scenario: 收盘后生成对账视图
- **WHEN** 系统汇总当日执行事件
- **THEN** 系统 SHALL 能按 ticket 和 symbol 聚合成交结果
- **THEN** 汇总结果 SHALL 可用于手机端复盘摘要和桌面端核对
