## ADDED Requirements

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
