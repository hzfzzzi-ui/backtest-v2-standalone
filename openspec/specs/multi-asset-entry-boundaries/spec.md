# multi-asset-entry-boundaries Specification

## Purpose
TBD - created by archiving change multi-asset-entry-boundaries. Update Purpose after archive.
## Requirements
### Requirement: 系统必须为每次正式运行声明 canonical asset scope
系统 MUST 要求桌面运行入口、study 定义、generated thin script 和 CLI 运行入口都能解析出 canonical `asset_scope`。系统 SHALL NOT 长期把“未声明资产范围”视为正式主路径的可接受输入。

#### Scenario: 桌面端发起运行
- **WHEN** 桌面端发起正式实验运行
- **THEN** 运行请求 MUST 能解析出 canonical `asset_scope`
- **THEN** 后端 SHALL NOT 继续依赖 A 股隐式默认来判断本次运行的资产语义

#### Scenario: study 发起运行
- **WHEN** `study_run` 执行某个 active study
- **THEN** 该 study MUST 能声明或解析出 canonical `asset_scope`
- **THEN** generated thin script MUST 只透传该资产范围，而 SHALL NOT 自己推断市场语义

### Requirement: 系统必须把 asset scope 解析为薄 asset profile 和 market profile
系统 MUST 将入口 `asset_scope` 解析为 canonical `asset_profile` 与 `market_profile`，并作为 runtime compile、universe resolver、provider route 和结果面摘要的共同真相。

#### Scenario: 解析当前 A 股主线
- **WHEN** 系统执行当前 `baseline_V10.1`
- **THEN** `asset_scope` MUST 解析为当前唯一正式 A 股 canonical profile
- **THEN** 解析结果 MUST 不改变 `V10.1` 的运行行为

#### Scenario: 未支持的资产范围
- **WHEN** 运行请求声明了尚未正式接入的 `asset_scope`
- **THEN** 系统 MUST 返回显式 unsupported error
- **THEN** 系统 SHALL NOT 静默回退到 A 股 profile

### Requirement: A 股专有市场假设必须作为 market profile 显式存在
系统 MUST 将交易日历、lot 规则、停牌语义、ST 语义、行业/成分数据依赖和 benchmark 家族等 A 股专有假设隔离为显式 `market_profile`，而 SHALL NOT 继续把这些假设散落为默认全局行为。

#### Scenario: A 股运行使用显式 market profile
- **WHEN** 系统运行 A 股 profile
- **THEN** 停牌、ST、lot size 和 benchmark 家族 MUST 通过 market profile 或对应 adapter 提供
- **THEN** 这些规则 SHALL NOT 仅通过隐式全局默认生效

#### Scenario: 未来新资产接入前
- **WHEN** 系统尚未正式实现某个新资产的 market profile adapter
- **THEN** 系统 MUST 在入口边界上明确缺失
- **THEN** 系统 SHALL NOT 复用 A 股规则假装支持该资产

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

### Requirement: 系统必须正式解析 `cn_etf` canonical asset profile
系统 MUST 允许请求入口、runtime compile、manifest 和 snapshot 正式解析 `asset_scope='cn_etf'`，并输出稳定的 `asset_context`。该 `asset_context` MUST 至少包含 `asset_scope`、`asset_profile_id`、`asset_family`、`asset_class`、`market_profile_id` 和 `execution_profile_id`。

#### Scenario: 解析 A 股 ETF 资产边界
- **WHEN** 运行请求、study 或历史 manifest 显式声明 `asset_scope='cn_etf'`
- **THEN** 系统 MUST 解析出 canonical ETF `asset_context`
- **THEN** 该 `asset_context` MUST 不得回退为 `cn_a_equity`

#### Scenario: ETF 入口沿用中国大陆市场执行壳
- **WHEN** 系统解析 `cn_etf` 资产范围
- **THEN** `asset_context` MUST 暴露中国大陆市场交易日历和 `T+1 / NEXT_OPEN / lot=100` 的执行语义
- **THEN** 系统 MUST 不把股票特有过滤或股票池语义当成 ETF 默认真相
