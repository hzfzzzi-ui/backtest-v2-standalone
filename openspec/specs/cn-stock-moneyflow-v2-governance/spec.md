# cn-stock-moneyflow-v2-governance Specification

## Purpose
浠?2026-03-22 褰掓。鍙樻洿鎭㈠鐨勪富瑙勬牸銆?
## Requirements

### Requirement: `moneyflow` MUST 作为 `pit_stock_moneyflow_v2` 独立侧表维护
系统 MUST 将 `moneyflow` 维护为独立侧表 `pit_stock_moneyflow_v2`，并 SHALL NOT 将 `moneyflow_*` 字段并入 `pams_ohlcv_daily_v2` 的主表硬合同。

#### Scenario: 资金流按 v2 主键对齐入库
- **WHEN** `Tushare moneyflow` 存在与 `pams_ohlcv_daily_v2` 相同的 `symbol + trade_date`
- **THEN** 系统 MUST 将该记录写入 `pit_stock_moneyflow_v2`

#### Scenario: 资金流记录没有主表键时不进入正式侧表
- **WHEN** 原始 `moneyflow` 存在某个 `symbol + trade_date`，但 `pams_ohlcv_daily_v2` 中不存在对应主键
- **THEN** 系统 SHALL NOT 将该记录写入正式侧表
- **THEN** 系统 MUST 将该样本记录为 `raw_only_not_in_master` 异常

### Requirement: `moneyflow` 缺失 MUST 被视为源缺失而非零值
系统 MUST 将 `moneyflow` 的覆盖缺口和 `net_mf_*` 空值视为源缺失，系统 SHALL NOT 以 `0`、前值填充或其他推断值替代。

#### Scenario: `net_mf_*` 为空时保留空值
- **WHEN** 资金流侧表行存在，但 `net_mf_vol` 或 `net_mf_amount` 为空
- **THEN** 系统 MUST 保持该字段为空
- **THEN** 系统 MUST 将该记录标记为 `net_fields_present=false`

#### Scenario: 整日无覆盖时生成覆盖异常
- **WHEN** 某个开市日 `moneyflow` 对 `v2` 主表的覆盖率为 `0`
- **THEN** 系统 MUST 在逐日审计中将该日标记为资金流整日缺失

### Requirement: `moneyflow` 研究使用 MUST 受覆盖率白名单约束
系统 MUST 为 `moneyflow` 提供逐日覆盖率和净额字段非空覆盖率门槛，只有达标日期才允许进入默认研究白名单。

#### Scenario: 行覆盖率不达标的日期不得进入默认白名单
- **WHEN** 某个交易日的 `moneyflow` 行覆盖率低于预设门槛
- **THEN** 系统 MUST 将该日排除在默认研究白名单之外

#### Scenario: `net_mf_amount` 非空覆盖率不达标的日期不得进入默认白名单
- **WHEN** 某个交易日的 `net_mf_amount` 非空覆盖率低于预设门槛
- **THEN** 系统 MUST 将该日排除在默认研究白名单之外
