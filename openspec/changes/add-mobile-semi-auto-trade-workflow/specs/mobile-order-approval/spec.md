## ADDED Requirements

### Requirement: 手机端必须支持确认、驳回和改单数量
系统 MUST 允许用户对单条或成组建议执行确认、驳回和改单数量。确认类动作 MUST 在提交前经过二次确认，且最终提交内容 SHALL 明确记录是“原始目标”还是“人工修改后数量”。

#### Scenario: 用户确认原始建议
- **WHEN** 用户选择确认某条建议且未修改数量
- **THEN** 系统 SHALL 要求二次确认
- **THEN** 二次确认完成后 SHALL 生成待执行指令

#### Scenario: 用户修改数量后确认
- **WHEN** 用户修改建议数量或目标仓位后提交确认
- **THEN** 系统 SHALL 记录原始建议值和修改后值
- **THEN** 生成的待执行指令 SHALL 显式标记为“人工调整”

#### Scenario: 用户驳回建议
- **WHEN** 用户对建议执行驳回
- **THEN** 系统 SHALL 记录驳回原因、操作者和时间
- **THEN** 该建议 SHALL NOT 进入待执行队列

### Requirement: 系统必须为每次确认生成可审计的 approval ticket
每一笔被确认的移动端指令 MUST 生成唯一的 `approval ticket`。该 ticket SHALL 至少包含来源实验、信号日期、股票标识、动作类型、原始建议、最终确认值、确认人、确认时间、二次确认标记和幂等键。

#### Scenario: 正常生成 approval ticket
- **WHEN** 用户完成合法确认流程
- **THEN** 系统 SHALL 创建唯一 ticket id
- **THEN** 系统 SHALL 将该 ticket 写入 append-only 审计与待执行清单

#### Scenario: 重复提交同一确认请求
- **WHEN** 客户端使用同一幂等键重复提交确认请求
- **THEN** 系统 SHALL 返回已存在的 ticket
- **THEN** 系统 SHALL NOT 生成重复待执行指令

### Requirement: 桌面执行器只可消费已批准且未失效的待执行指令
系统 MUST 只允许桌面执行器读取状态为 `approved_pending` 的 ticket。已驳回、已撤回、已执行、已过期或被风控拦截的 ticket SHALL NOT 再次进入执行队列。

#### Scenario: 执行器拉取待执行指令
- **WHEN** 桌面执行器查询待执行清单
- **THEN** 系统 SHALL 仅返回可执行状态的 ticket
- **THEN** 返回结果 SHALL 包含足够的审计字段供执行器回写结果

#### Scenario: ticket 超时失效
- **WHEN** ticket 超过允许执行窗口仍未被执行器接单
- **THEN** 系统 SHALL 将其标记为 `expired`
- **THEN** 手机端 SHALL 显示该状态并允许用户重新确认或撤销
