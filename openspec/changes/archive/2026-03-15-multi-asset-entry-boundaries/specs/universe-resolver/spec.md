## ADDED Requirements

### Requirement: Universe resolver 必须先按 asset family 分发
系统 MUST 让 universe resolver 入口先消费 canonical `asset_profile`，再把解析流程分发到对应的 asset-family resolver。当前 A 股 resolver SHALL 只是其中一个 adapter。

#### Scenario: 运行 A 股 universe 解析
- **WHEN** runtime compile 传入当前 canonical A 股 asset profile
- **THEN** resolver MUST 路由到 A 股 adapter
- **THEN** 解析结果 MUST 与当前 `V10.1` universe 语义等价

#### Scenario: 运行未支持资产的 universe 解析
- **WHEN** runtime compile 传入尚未实现的 asset profile
- **THEN** resolver MUST 返回显式 unsupported error
- **THEN** 系统 SHALL NOT 继续复用 A 股 resolver

### Requirement: A 股 resolver 规则必须作为 asset-specific adapter 保留
系统 MUST 将 `ALL_A`、`HS300_ZZ500`、`INDUSTRY`、`CUSTOM` 等现有 A 股 universe 解析规则保留在 A 股 adapter 内，而 SHALL NOT 把它们继续定义成默认全局 universe 主语义。

#### Scenario: A 股行业模式解析
- **WHEN** A 股 profile 使用 `INDUSTRY` 模式
- **THEN** 系统 MUST 继续使用现有 A 股行业历史数据规则
- **THEN** 这些规则 SHALL 仅在 A 股 adapter 内生效
