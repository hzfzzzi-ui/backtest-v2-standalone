## ADDED Requirements

### Requirement: ETF beta sleeve 必须消费 canonical ETF contract projection
`cn-etf-beta-sleeve` 的 provider、runtime summary、artifact finalize 和 audit 摘要 MUST 统一消费 canonical ETF contract projection。该 sleeve SHALL NOT 再把同一批 ETF 配置字段分别在多个层级独立归一化或重复命名。

#### Scenario: provider 构建 ETF beta 运行时
- **WHEN** ETF beta provider 读取 ETF sleeve 配置
- **THEN** provider MUST 读取 canonical ETF contract projection
- **THEN** provider SHALL NOT 再从原始配置对象手工拼装第二套字段语义

#### Scenario: artifact 与 audit 暴露 ETF sleeve 摘要
- **WHEN** 系统输出 `run_meta.json`、`audit.json` 或 experiment surface
- **THEN** ETF sleeve 摘要 MUST 来自 canonical ETF contract projection
- **THEN** artifact finalize 和 research audit SHALL NOT 各自维护独立的 ETF 字段映射表

### Requirement: ETF beta sleeve 必须区分 raw evidence 与 formal truth
ETF provider MAY 继续输出原始 diagnostics 作为调试证据，但正式 artifact、audit 和 snapshot MUST 只暴露 formal ETF truth。调试证据 SHALL NOT 被前端或 audit 当成唯一正式真相源。

#### Scenario: provider diagnostics 与 formal truth 并存
- **WHEN** ETF provider 产生日级 diagnostics
- **THEN** diagnostics MAY 保留调试细节
- **THEN** formal ETF truth MUST 经过 canonical projection 输出，而不是由前端或 audit 直接读取 raw diagnostics
