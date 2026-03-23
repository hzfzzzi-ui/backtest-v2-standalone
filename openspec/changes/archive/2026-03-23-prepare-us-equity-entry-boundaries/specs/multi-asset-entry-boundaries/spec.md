## ADDED Requirements

### Requirement: 系统必须正式解析并暴露 `us_equity` canonical asset profile
系统 MUST 允许运行入口、runtime compile、manifest 和 snapshot 正式解析 `us_equity` 作为 canonical `asset_scope`，并产出稳定的 `asset_profile` / `market_profile` / `execution_profile` 摘要。系统 SHALL NOT 因为 `us_equity` 尚未接入数据与交易 adapter，而继续把该 scope 视为未知输入。

#### Scenario: 解析美股个股资产边界
- **WHEN** 运行请求、study 或已有 manifest 明确声明 `asset_scope='us_equity'`
- **THEN** 系统 MUST 产出 canonical `asset_context`
- **THEN** 该 `asset_context` MUST 包含 `asset_scope`、`asset_profile_id`、`asset_family` 和 `market_profile_id`

### Requirement: 通用入口不得继续把 `cn_a_equity` 作为隐式全局默认
系统 MUST 要求 request contract、runtime compile、frontend payload 和 snapshot bridge 显式透传或解析资产范围。通用入口 SHALL NOT 再在未检查已有配置、manifest 或 request 的情况下，直接写入 `cn_a_equity` 作为默认资产真相。

#### Scenario: 兼容老 A 股入口但不再硬编码默认
- **WHEN** 当前 A 股 baseline 或历史 artifact 未显式声明 `asset_scope`
- **THEN** 系统 MAY 通过已有 baseline/config/manifest 兼容解析出 `cn_a_equity`
- **THEN** 通用入口 SHALL NOT 无条件把空值重写成 `cn_a_equity`

### Requirement: 未实现资产 adapter 时必须显式 unsupported
系统 MUST 区分“资产边界已可解析”和“该资产已可运行”。对于尚未实现数据、universe、sync 或 execution adapter 的资产，系统 MUST 返回显式 unsupported error 或 status，而 SHALL NOT 静默回退到 A 股主路径。

#### Scenario: 美股 scope 进入未实现运行路径
- **WHEN** `asset_scope='us_equity'` 进入当前仅支持 A 股的 resolver、sync 或 execution 入口
- **THEN** 系统 MUST 明确返回 unsupported
- **THEN** 系统 SHALL NOT 自动复用 A 股规则继续运行
