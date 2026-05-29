# market_data_vendor_raw@1

## 定位

`market_data_vendor_raw@1` 约束市场数据供应商进入研究平台的第一落点。正式路径是：

`vendor API / files -> raw vendor tables -> quality checks -> canonical_market -> market_data_access`

上层研究、回测、前端、live package publisher 不得直接消费 Tushare、iFinD 或其他供应商客户端返回值。

## 当前状态

| vendor | status | raw namespace | 说明 |
|---|---|---|---|
| Tushare | implemented | `raw_tushare_*` | 当前 A 股主数据源，已通过 `update_pams_ohlcv_daily_v2_raw` 进入 raw vendor 层 |
| iFinD | reserved | `raw_ifind_*` | 未实现正式同步器；接入前不得被宣传为已实现数据源 |
| Other vendors | reserved | `raw_<vendor>_*` | 新供应商必须先补 source matrix、raw 表、同步器、质量检查和回滚说明 |

## Tushare Raw Tables

当前实现的 Tushare raw vendor 表包括：

- `raw_tushare_stock_basic`
- `raw_tushare_trade_cal`
- `raw_tushare_daily`
- `raw_tushare_adj_factor`
- `raw_tushare_daily_basic`
- `raw_tushare_suspend_d`
- `raw_tushare_stk_limit`
- `raw_tushare_moneyflow`

这些表只表达供应商原始落地结果，不是 canonical market truth。

## iFinD 接入纪律

iFinD 可以作为后续供应商接入，但上线前必须满足：

- 使用 `raw_ifind_*` 命名空间先落 raw vendor 层
- source matrix 明确字段主源、补源、审计源和适用阶段
- 质量检查通过后才能进入 `canonical_market`
- 上层仍只能通过 `market_data_access` 消费 canonical 数据
- 未完成同步器、质量检查和回滚脚本前，状态必须保持 `reserved`

## 禁止事项

- 禁止上层策略直接调用供应商 SDK 或读取 raw vendor 表。
- 禁止把供应商补源值与 canonical 主值混写但不保留 `*_source` / `*_confidence`。
- 禁止把 iFinD、TradingView、券商或文件导入结果绕过 raw vendor 层直接写入 canonical。
