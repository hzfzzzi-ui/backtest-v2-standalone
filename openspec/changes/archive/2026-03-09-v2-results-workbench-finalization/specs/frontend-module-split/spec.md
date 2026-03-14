## MODIFIED Requirements

### Requirement: 结果模块拆分必须以单一 DOM ownership 为目标

前端结果相关模块拆分不仅 SHALL 将逻辑拆到独立文件，还 MUST 确保结果区只有一个渲染 owner。多个模块 SHALL NOT 同时渲染或 patch 同一块可见结果 DOM。

#### Scenario: 结果区模块已拆分但仍有双写
- **WHEN** 结果概览、图表、漏斗或交易明细已拆到多个文件
- **THEN** 系统 MUST 指定唯一的结果区 owner
- **THEN** 其他模块仅 MAY 负责数据读取、归一化或 fallback

#### Scenario: legacy helper 保留
- **WHEN** 仍保留 legacy helper 以便回退
- **THEN** 这些 helper SHALL NOT 在结果工作台挂载成功后继续写入可见结果区 DOM
