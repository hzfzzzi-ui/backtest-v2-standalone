# cn-stock-daily-v2-canonical Specification

## Purpose
浠?2026-03-22 褰掓。鍙樻洿鎭㈠鐨勪富瑙勬牸銆?
## Requirements

### Requirement: `pams_ohlcv_daily_v2` 必须以 raw daily 观测行为主表行来源
系统 MUST 使用 raw `daily` 观测到的 `ts_code + trade_date` 组合作为 `pams_ohlcv_daily_v2` 的主表行来源，并以 `pit_security_master` 作为合法证券边界过滤条件。系统 SHALL NOT 在没有显式停牌原始源的前提下，仅凭 `security master x trade_cal` 全展开去合成所有应有行。

#### Scenario: 合法观测行进入 v2
- **WHEN** raw `daily` 中存在某个 `ts_code + trade_date`，且该证券在 `pit_security_master` 中对该日处于有效上市区间
- **THEN** 系统 MUST 将该记录构建进 `pams_ohlcv_daily_v2`

#### Scenario: 非法或未知证券被拒绝
- **WHEN** raw `daily` 中出现不在 `pit_security_master` 范围内的证券记录
- **THEN** 系统 SHALL NOT 将该记录直接写入 `pams_ohlcv_daily_v2`
- **THEN** 系统 MUST 将该记录写入异常审计输出

### Requirement: `pams_ohlcv_daily_v2` 必须保留 v1 兼容字段并显式标记源覆盖
系统 MUST 让 `pams_ohlcv_daily_v2` 保持与 `pams_ohlcv_daily` 兼容的核心字段语义，包括 OHLCV、`adj_factor`、`limit_up/down`、`is_suspended` 和 `daily_basic` 基础字段；同时系统 MUST 新增 source presence 与构建批次标记字段，以支持追溯。

#### Scenario: `daily_basic` 字段按同键对齐
- **WHEN** raw `daily_basic` 中存在与 v2 主表相同的 `ts_code + trade_date`
- **THEN** 系统 MUST 将 `turnover_rate`、`turnover_rate_f` 及其他约定字段按同键写入 `pams_ohlcv_daily_v2`

#### Scenario: `daily_basic` 缺失不被静默伪造
- **WHEN** v2 主表存在某个 `symbol + trade_date`，但 raw `daily_basic` 没有对应记录
- **THEN** 系统 SHALL 保持这些字段为空
- **THEN** 系统 MUST 在审计输出中记录该日 `daily_basic` 缺口

### Requirement: `moneyflow` 必须以 v2 主键对齐到独立侧表
系统 MUST 将 `moneyflow` 构建到独立的 `pit_stock_moneyflow_v2`，并以 `pams_ohlcv_daily_v2` 的 `symbol + trade_date` 作为消费主键边界。

#### Scenario: v2 主键内的资金流记录入库
- **WHEN** raw `moneyflow` 中存在与 `pams_ohlcv_daily_v2` 相同的 `symbol + trade_date`
- **THEN** 系统 MUST 将该记录写入 `pit_stock_moneyflow_v2`

#### Scenario: raw moneyflow 超出主表主键
- **WHEN** raw `moneyflow` 中存在 `symbol + trade_date`，但 `pams_ohlcv_daily_v2` 不存在对应主键
- **THEN** 系统 SHALL NOT 将该记录直接视为主表已对齐
- **THEN** 系统 MUST 将该记录输出为 raw-only 异常

### Requirement: `v2` 构建必须输出覆盖率和 `v1/v2` 差异审计
系统 MUST 对 `pams_ohlcv_daily_v2` 输出逐交易日构建审计、侧表对齐审计和 `pams_ohlcv_daily` 对比审计，至少包含行数差异、关键字段空值率和异常样本。

#### Scenario: 逐交易日构建审计
- **WHEN** 系统完成某一日期窗口的 `v2` 构建
- **THEN** 系统 MUST 输出该窗口内每个 `trade_date` 的 eligible 证券数、raw daily 数、v2 主表数、`daily_basic` 对齐数和 `moneyflow` 对齐数

#### Scenario: `v1/v2` 差异摘要
- **WHEN** 系统完成某一日期窗口的 `v2` 构建
- **THEN** 系统 MUST 输出 `pams_ohlcv_daily` 与 `pams_ohlcv_daily_v2` 的逐日行数差异和样本差异

### Requirement: `pams_ohlcv_daily_v2` 必须通过 shadow 配置消费，而不改变默认运行时
系统 MUST 提供显式 shadow 配置或等价运行时入口，使 V10.1 可以读取 `pams_ohlcv_daily_v2` 做平行验证；系统 SHALL NOT 默认切换现有 `stocks_table`。

#### Scenario: Shadow 运行使用 v2
- **WHEN** 用户显式选择 `v2` shadow 配置运行 V10.1
- **THEN** 系统 MUST 读取 `pams_ohlcv_daily_v2` 作为股票日频来源
- **THEN** 默认配置行为 MUST 保持不变
