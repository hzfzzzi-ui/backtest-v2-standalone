## Why

当前系统已经具备 A 股日频 OHLCV 主链路，但“显式换手率”和“按主动买卖单且带金额分档的资金流”仍未形成可审计的库表口径。继续把这两类研究输入混在 `pams_ohlcv_daily` 主表或依赖临时抓取，会放大口径漂移、历史回填不完整和研究不可复现的风险。

本次新增独立侧表有三个直接收益：
- 把 `daily_basic` 的显式换手率和 `moneyflow` 的主动买卖单分档资金流固定为独立口径。
- 为 `2007-01-04` 到当前最新可得交易日的历史回填与后续增量同步提供稳定边界。
- 在回填完成后，能对侧表覆盖率做独立审计，而不是把“有数据”误判成“覆盖充分”。

## What Changes

- 新增 `pit_stock_daily_basic`，按 `symbol + trade_date` 存储 `turnover_rate`、`turnover_rate_f`。
- 新增 `pit_stock_moneyflow`，按 `symbol + trade_date` 存储 Tushare `moneyflow` 的四档主动买卖量额与净流入字段。
- 新增两条托管回填脚本，覆盖 `2007-01-04` 到当前最新可得交易日，并支持后续增量更新。
- 新增覆盖率审计脚本，按交易日对比 `pams_ohlcv_daily`、`pit_stock_daily_basic`、`pit_stock_moneyflow` 的行数，输出覆盖率、最差覆盖交易日和缺口样本。
- 保持现有 `pams_ohlcv_daily`、provider 默认读取路径、baseline 配置与回测口径不变；本次不把新字段并入主表。

## Capabilities

### New Capabilities
- `cn-daily-feature-side-tables`: 为 `CN_A` 引入可审计的换手率侧表、资金流侧表和覆盖率审计链路。

### Modified Capabilities
- 无。

## Impact

- 数据库：新增两张 A 股日频侧表及其索引、唯一键与时间戳字段。
- 数据接入：新增 Tushare `daily_basic`、`moneyflow` 的历史回填和增量同步链路。
- 运维：新增覆盖率审计脚本与审计产物，回填完成后可直接验证缺口规模和缺口样本。
- 研究边界：本次只落库与审计，不修改 baseline 主逻辑和主消费路径。
