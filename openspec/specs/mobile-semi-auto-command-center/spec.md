# mobile-semi-auto-command-center Specification

## Purpose
TBD - created by archiving change add-mobile-semi-auto-trade-workflow. Update Purpose after archive.
## Requirements
### Requirement: 手机端必须展示可审批的结构化交易指挥卡片
系统 MUST 将最新实验、执行预览、当前持仓和市场风险摘要整合为面向手机端的交易指挥卡片。每条建议 SHALL 至少包含动作类型、股票标识、目标仓位或建议数量、主要原因标签、止损/退出标签、信号日期和数据新鲜度说明。

#### Scenario: 最新信号快照可用
- **WHEN** 系统能够读取最新实验产物并生成执行预览
- **THEN** 手机端 SHALL 展示买入、卖出、持有三类结构化卡片
- **THEN** 每条卡片 SHALL 明确标记其为“下一次执行建议”而非已成交事实

#### Scenario: 数据新鲜度不足
- **WHEN** 最新实验、执行预览或市场快照超过设定的新鲜度阈值
- **THEN** 手机端 SHALL 显示显式的“数据过期”提示
- **THEN** 系统 SHALL 阻止用户把过期建议直接推进到确认提交流程

### Requirement: 手机端必须区分“系统建议”与“用户已确认动作”
系统 MUST 在移动端同时展示两类状态：一类是只读的系统建议，另一类是用户已经确认、驳回或修改后的待执行动作。系统 SHALL NOT 用已确认状态覆盖原始建议事实。

#### Scenario: 用户已确认某条建议
- **WHEN** 某条建议已经生成 `approval ticket`
- **THEN** 手机端 SHALL 在对应建议上显示“已确认待执行”状态
- **THEN** 原始建议卡片 SHALL 仍可追溯其来源实验和原始目标仓位

#### Scenario: 用户驳回某条建议
- **WHEN** 用户驳回某条建议
- **THEN** 手机端 SHALL 将其标记为“已驳回”
- **THEN** 系统 SHALL 保留驳回原因与时间戳供后续复盘使用

### Requirement: 手机端必须暴露不可执行的阻断原因
当某条建议因为风险门控、数据过期、重复提交或执行器不可用而不可继续确认时，系统 MUST 返回结构化阻断原因。手机端 SHALL 使用阻断原因禁用对应操作入口，而不是只返回通用报错。

#### Scenario: 风控拦截建议动作
- **WHEN** 某条建议命中风控规则或确认前检查失败
- **THEN** 系统 SHALL 返回结构化阻断码和可读说明
- **THEN** 手机端 SHALL 对该建议禁用确认按钮并显示阻断原因

