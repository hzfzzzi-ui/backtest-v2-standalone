## ADDED Requirements

### Requirement: SignalProvider 和 route registry 必须显式消费 asset profile
系统 MUST 要求 signal provider façade、route registry 和 runtime route 选择显式消费 canonical `asset_profile` 或 `market_profile`。这些模块 SHALL NOT 再把 A 股作为隐式全局前提。

#### Scenario: 运行当前 A 股 provider
- **WHEN** runtime route 选择当前 A 股 provider
- **THEN** route 选择 MUST 基于 canonical A 股 asset profile
- **THEN** 选择结果 MUST 保持当前 `V10.1` provider 行为不变

#### Scenario: 运行未支持资产
- **WHEN** route registry 收到尚未实现的 asset profile
- **THEN** 系统 MUST 明确返回 unsupported error
- **THEN** 系统 SHALL NOT 静默复用 A 股 provider

### Requirement: Provider façade 不得继续内嵌资产 family 的隐式默认
系统 MUST 要求 provider façade 的 `precompute()` 和 `day_signals()` 入口显式可见资产上下文。与资产 family 强绑定的约束和 helper MUST 通过 profile/adapter 注入，而不是硬编码为默认全局行为。

#### Scenario: A 股特有约束被隔离
- **WHEN** provider 需要使用 A 股特有的 lot、停牌或 benchmark 规则
- **THEN** 这些规则 MUST 通过 asset/market profile 或对应 helper 提供
- **THEN** façade 文件 SHALL NOT 继续把这些规则写成无条件全局逻辑
