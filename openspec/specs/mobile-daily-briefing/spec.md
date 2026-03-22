# mobile-daily-briefing Specification

## Purpose
TBD - created by archiving change add-mobile-semi-auto-trade-workflow. Update Purpose after archive.
## Requirements
### Requirement: 系统必须提供开盘前待办摘要
系统 MUST 在交易日开始前生成面向移动端的开盘前摘要，至少包含待确认建议数量、上一个交易日未完成 ticket、主要风险提示和数据新鲜度状态。

#### Scenario: 存在待确认建议
- **WHEN** 开盘前存在新的可确认建议
- **THEN** 系统 SHALL 生成开盘前摘要
- **THEN** 摘要 SHALL 明确列出待确认数量和主要风险提示

#### Scenario: 不存在新的待确认建议
- **WHEN** 开盘前没有新的可确认建议
- **THEN** 系统 SHALL 仍返回结构化摘要
- **THEN** 摘要 SHALL 明确标记“无新增待确认动作”

### Requirement: 系统必须提供执行异常通知摘要
系统 MUST 基于执行事件生成异常通知摘要，至少覆盖拒单、超时未执行、部分成交、风控拦截和回写失败。该摘要 SHALL 可供站内提醒、PWA 提醒或其他私有通知渠道复用。

#### Scenario: 出现执行异常
- **WHEN** 某张 ticket 进入 `rejected`、`expired` 或 `partially_filled` 等异常相关状态
- **THEN** 系统 SHALL 生成结构化异常摘要
- **THEN** 摘要 SHALL 包含 ticket 标识、异常类型和建议处理动作

### Requirement: 系统必须生成收盘后复盘摘要
系统 MUST 在收盘后生成移动端复盘摘要，至少包含当日确认单数量、已执行数量、未完成数量、主要成交偏差、持仓变化和可追溯的实验来源。

#### Scenario: 收盘后存在已执行和未完成指令
- **WHEN** 系统汇总当日 ticket 与 execution events
- **THEN** 系统 SHALL 生成收盘后复盘摘要
- **THEN** 摘要 SHALL 同时展示完成情况、异常情况和来源实验标识

#### Scenario: 收盘后无任何移动端操作
- **WHEN** 当日没有新的确认或执行事件
- **THEN** 系统 SHALL 返回空操作复盘摘要
- **THEN** 摘要 SHALL 明确说明“当日无移动端交易操作”

