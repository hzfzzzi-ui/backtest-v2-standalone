## Why

当前 A 股系统已经有 `update_pams_ohlcv_daily` 写库链路，但仍依赖人工触发，缺少“每天定时补到前一交易日”的正式机制，也没有对前端暴露明确的最新同步日期。结果是桌面端无法直接判断数据库是否新鲜，数据陈旧会变成隐性风险，损害可信性、可审计性和日常使用体验。

## What Changes

- 新增 A 股日线数据定时同步能力：系统按配置时间每天自动尝试把 `pams_ohlcv_daily` 补到前一交易日，默认复用现有 `update_pams_ohlcv_daily` 写库逻辑，而不是再造一套抓数实现。
- 新增同步真相源：系统为每次日更写入结构化同步状态，至少记录目标交易日、最新成功同步日期、运行状态、运行时间、行数摘要和错误摘要。
- 新增前端显性 freshness 状态：桌面 A 股系统必须明确显示“当前最新同步日期”，并能区分 fresh、stale、failed、never-synced 等状态。
- 新增轻量状态接口：前端通过正式 API 读取同步状态，禁止在页面侧直接猜数据库日期或自行推断同步是否成功。

## Capabilities

### New Capabilities
- `cn-daily-data-sync`: 规范 A 股日线数据的定时同步、目标交易日判定、幂等落库和同步状态落盘/落库。
- `market-data-freshness-status`: 规范桌面端可读取的市场数据 freshness 状态面，包括最新成功同步日期、当前状态和前端显性展示语义。

### Modified Capabilities

## Impact

- 影响后端数据链路：`backend/cli/managed/update_pams_ohlcv_daily.py`、新的调度/状态模块、数据库状态表或等价持久化真相源。
- 影响 HTTP 边界：`backend/api/backtest_v2/routes/market_data.py` 及对应实现需要新增市场数据同步状态接口。
- 影响前端桌面壳：`frontend/assets/js/api-client.js`、`frontend/assets/js/backtest_v2.js` 与状态中心/顶部状态展示需要消费新的 freshness 状态。
- 影响部署配置：`docker-compose.yml` 与环境变量需要为定时同步时间、启停开关、Tushare token 等提供正式入口。
