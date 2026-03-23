## ADDED Requirements

### Requirement: Universe resolver 入口必须显式消费 canonical asset profile
系统 MUST 让 `resolve_universe_by_mode()` 先解析 canonical `asset_profile`，再把解析请求分发到对应 asset-family adapter。当前 A 股 resolver 只是 `cn_a_equity` adapter，而 SHALL NOT 继续承担全局默认 universe 语义。

#### Scenario: 运行当前 A 股 universe
- **WHEN** `asset_scope='cn_a_equity'`
- **THEN** resolver MUST 路由到当前 A 股 adapter
- **THEN** 返回 symbols 与元数据 MUST 保持当前 A 股语义不变

### Requirement: 未实现资产的 universe 请求必须显式失败
系统 MUST 对未实现的 asset-family universe 请求返回显式 unsupported error，并带上 `asset_scope` 与 `universe_mode` 元信息。系统 SHALL NOT 静默复用 A 股 `ALL_A / HS300_ZZ500 / INDUSTRY / CUSTOM` 逻辑。

#### Scenario: 美股个股请求进入当前 resolver
- **WHEN** `asset_scope='us_equity'`
- **THEN** resolver MUST 返回可审计的 unsupported error
- **THEN** error 元信息 MUST 暴露 `asset_scope='us_equity'`
