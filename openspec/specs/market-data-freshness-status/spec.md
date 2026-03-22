# market-data-freshness-status Specification

## Purpose
浠?2026-03-22 褰掓。鍙樻洿鎭㈠鐨勪富瑙勬牸銆?
## Requirements

### Requirement: 系统必须暴露 A 股数据同步状态接口
系统 MUST 通过正式 HTTP 接口暴露 A 股市场数据同步状态，供桌面前端读取。该接口 MUST 返回最新成功同步日期、目标交易日、当前状态和最近一次运行摘要；前端 SHALL NOT 直接猜测数据库日期或自行推断同步状态。

#### Scenario: 读取已成功同步的状态
- **WHEN** 前端请求市场数据同步状态接口，且系统已至少完成一次成功同步
- **THEN** 接口 MUST 返回 `latest_success_trade_date`
- **THEN** 接口 MUST 同时返回 `target_trade_date`、当前 `status` 和最近一次运行时间摘要

#### Scenario: 系统尚未成功同步
- **WHEN** 前端请求市场数据同步状态接口，但系统还没有任何成功同步记录
- **THEN** 接口 MUST 返回 `never_synced` 或等价显式状态
- **THEN** 接口 SHALL NOT 伪造最新同步日期

#### Scenario: 调度禁用或当前状态异常
- **WHEN** 调度器被禁用，或最近一次同步失败且最新成功日期仍落后于目标交易日
- **THEN** 接口 MUST 返回 `disabled`、`failed`、`stale` 或等价显式状态
- **THEN** 接口 MUST 返回可供前端展示的说明信息，而不是只给空值

#### Scenario: 库内旧交易日历停更但活交易日历可用
- **WHEN** 系统中的旧交易日历表已停更，但活交易日历源仍可读取
- **THEN** 接口 MUST 返回基于活交易日历源解析的 `target_trade_date`
- **THEN** 接口 SHALL NOT 因旧表落后而把 freshness 状态错误地判定为“已新鲜”

### Requirement: 桌面 A 股系统必须显性展示最新同步日期
桌面 A 股系统 MUST 在主界面显性展示当前市场数据的最新同步日期，并在状态中心或等价状态面展示同步状态详情。前端 MUST 区分真实日期、未同步、失败、运行中和禁用状态，而 SHALL NOT 把缺失状态渲染为空白或误导性文案。

#### Scenario: 数据新鲜时展示最新同步日期
- **WHEN** 同步状态接口返回 `fresh` 且存在 `latest_success_trade_date`
- **THEN** 桌面 A 股系统 MUST 在显眼位置展示该日期
- **THEN** 状态中心 MUST 能查看该日期对应的目标交易日和最近一次运行摘要

#### Scenario: 数据陈旧或失败时展示显式状态
- **WHEN** 同步状态接口返回 `stale`、`failed`、`running`、`never_synced` 或 `disabled`
- **THEN** 桌面 A 股系统 MUST 显式展示该状态，而不是继续显示过期日期为“正常”
- **THEN** 状态中心 MUST 提供最近一次错误或 lag 信息，帮助用户判断是否需要人工介入
