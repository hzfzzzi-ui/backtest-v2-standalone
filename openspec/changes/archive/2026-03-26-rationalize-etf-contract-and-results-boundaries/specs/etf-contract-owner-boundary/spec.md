## ADDED Requirements

### Requirement: ETF contract 必须存在单一正式 owner
系统 MUST 为 ETF beta contract 提供单一正式 owner，用于统一承接 ETF 配置归一化、运行时 contract projection 和下游消费摘要。该 owner MUST 成为 ETF beta 字段语义的唯一正式解释来源。

#### Scenario: ETF beta 配置进入运行时
- **WHEN** 前端或 study definition 提交 ETF beta 配置
- **THEN** 系统 MUST 先经过 ETF contract owner 完成归一化
- **THEN** provider、artifact finalize 和 research audit MUST 消费归一化后的 canonical ETF contract

### Requirement: ETF contract 新字段不得继续多点手工透传
系统 SHALL NOT 在新增 ETF contract 字段时继续采用 `schema -> governed config -> provider diagnostics -> artifact finalize -> audit` 的多点手工透传模式。新字段 MUST 先进入 ETF contract owner，再由下游按统一投影消费。

#### Scenario: 新增 ETF 槽位或替换语义字段
- **WHEN** 系统新增 ETF contract 字段，例如槽位、替换模式或 deployability 语义
- **THEN** 该字段 MUST 先定义在 ETF contract owner
- **THEN** 下游模块 SHALL NOT 各自重新解释或重复归一化该字段

### Requirement: ETF contract owner 必须提供 canonical projection
ETF contract owner MUST 输出最小 canonical projection，至少覆盖 provider、artifact finalize、research audit 和 front-end snapshot 所需的 ETF sleeve 真相字段。

#### Scenario: 下游消费 ETF sleeve 摘要
- **WHEN** artifact finalize、research audit 或 result surface 需要 ETF sleeve 摘要
- **THEN** 系统 MUST 从 ETF contract owner 的 canonical projection 读取
- **THEN** 下游 SHALL NOT 直接从原始配置或 provider diagnostics 拼装第二份 ETF 真相
