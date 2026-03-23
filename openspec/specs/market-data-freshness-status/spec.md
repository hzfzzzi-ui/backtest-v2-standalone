# market-data-freshness-status Specification

## Purpose
规范市场数据 freshness 状态接口与桌面状态展示在 A 股场景下统一使用 V2 主线日期作为正式口径与新鲜度锚点。

## Requirements

### Requirement: 系统必须暴露基于 V2 主线的 A 股数据同步状态接口
系统 MUST 通过正式 HTTP 接口暴露 A 股市场数据同步状态，供桌面前端读取。该接口 MUST 返回最新成功同步日期、目标交易日、当前状态和最近一次运行摘要；前端 SHALL NOT 直接猜测数据库日期或自行推断同步状态。`latest_success_trade_date` 与 `latest_available_trade_date` MUST 基于 V2 主线口径计算，而 SHALL NOT 继续以 `pams_ohlcv_daily` 的 `MAX(trade_date)` 作为正式 freshness 锚点。

#### Scenario: 读取已成功同步的 V2 主线状态
- **WHEN** 前端请求市场数据同步状态接口，且系统已至少完成一次成功同步
- **THEN** 接口 MUST 返回基于 V2 主线锚点的 `latest_success_trade_date`
- **THEN** 接口 MUST 同时返回 `target_trade_date`、当前 `status` 和最近一次运行时间摘要

#### Scenario: 旧表日期领先于 V2 主线时不得误报 fresh
- **WHEN** `pams_ohlcv_daily` 的最新交易日新于 `pams_ohlcv_daily_v2` 或 `pit_stock_moneyflow_v2` 或 `pit_stock_moneyflow_v2_whitelist_daily`
- **THEN** 接口 SHALL NOT 因旧表日期更晚而把 freshness 状态判定为 `fresh`
- **THEN** 接口 MUST 继续返回基于 V2 主线锚点计算的 `latest_available_trade_date` 和对应 lag 状态

#### Scenario: 系统尚未成功同步时回退到 V2 主线数据库日期
- **WHEN** 前端请求市场数据同步状态接口，但系统还没有任何成功同步记录
- **THEN** 接口 MUST 返回 `never_synced` 或等价显式状态
- **THEN** 若数据库存在 V2 主线日期，接口 MUST 仅返回该 V2 主线日期，而不得伪造旧表日期为正式成功日期

### Requirement: 桌面 A 股系统必须显性展示 V2 主线最新同步日期
桌面 A 股系统 MUST 在主界面显性展示当前市场数据的最新同步日期，并在状态中心或等价状态面展示同步状态详情。前端 MUST 区分真实日期、未同步、失败、运行中和禁用状态，而 SHALL NOT 把缺失状态渲染为空白或误导性文案。该展示中的“最新同步日期” MUST 表示 V2 主线日期，而不是 legacy 兼容桥接表日期。

#### Scenario: 数据新鲜时展示 V2 主线最新同步日期
- **WHEN** 同步状态接口返回 `fresh` 且存在 `latest_success_trade_date`
- **THEN** 桌面 A 股系统 MUST 在显眼位置展示该 V2 主线日期
- **THEN** 状态中心 MUST 能查看该日期对应的目标交易日和最近一次运行摘要

#### Scenario: 数据陈旧或失败时显式展示主线口径异常
- **WHEN** 同步状态接口返回 `stale`、`failed`、`running`、`never_synced` 或 `disabled`
- **THEN** 桌面 A 股系统 MUST 显式展示该状态，而不是继续显示过期日期为“正常”
- **THEN** 状态中心 MUST 提供最近一次错误或 lag 信息，帮助用户判断是否需要人工介入

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
