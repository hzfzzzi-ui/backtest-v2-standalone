## ADDED Requirements

### Requirement: freshness status 接口必须显式携带资产范围
系统 MUST 让 market data freshness status 接口显式消费并返回 `asset_scope`，并把该值视为 freshness 语义的一部分。前端 SHALL NOT 再把不带资产范围的 freshness payload 解释为默认 A 股状态。

#### Scenario: A 股 freshness 状态返回资产范围
- **WHEN** 前端请求当前 A 股市场 freshness 状态
- **THEN** payload MUST 包含 `asset_scope='cn_a_equity'`
- **THEN** 相关 `sync_key` 和日期解释 MUST 与该资产范围一致

### Requirement: 未实现资产的 freshness status 必须显式 unsupported
系统 MUST 对尚未接入 freshness adapter 的资产返回可展示的 unsupported 状态与消息，而 SHALL NOT 继续回退到 A 股 mainline 日期。

#### Scenario: 美股 freshness 查询
- **WHEN** 前端请求 `asset_scope='us_equity'` 的 freshness 状态
- **THEN** 接口 MUST 返回 unsupported 状态与说明
- **THEN** `latest_success_trade_date` 与 `latest_available_trade_date` SHALL 为空
