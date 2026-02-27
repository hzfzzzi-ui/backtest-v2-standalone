## Why

当前 VECTOR 引擎直接使用 `pams_ohlcv_daily` 中的不复权（raw）OHLCV 价格计算技术指标和生成信号。当股票发生除权除息（送股、分红、配股）时，价格序列出现断裂（如平安银行 19.24→11.93），导致均线、ATR 等技术指标在除权日产生虚假信号。数据库已存储 `adj_factor`（后复权因子，99.8% 行非空），但引擎完全忽略该字段。前端 `wbPriceAdj` 控件（qfq/hfq/none 三档）也处于完全断开状态。

## What Changes

- **信号计算路径**：在 OHLCV 数据加载后、进入引擎前，根据用户选择的复权模式对 OHLCV 价格列乘以复权因子，使技术指标在连续价格序列上计算
- **成交执行路径**：保持使用不复权（raw）价格作为实际成交价，确保资金计算与真实市场一致
- **前端控件接通**：将 `wbPriceAdj`（前复权/后复权/不复权）控件接入请求参数链路，传递到引擎
- **数据提供层**：`pg_provider.load_ohlcv_daily()` 返回的 DataFrame 增加 `adj_factor` 列
- **复权转换层**：新增复权价格转换函数，支持 qfq/hfq/none 三种模式
- **产物可观测**：在 `run_meta` 中记录实际使用的复权模式，trades 表保留 raw_price 和 fill_price 以供对照

## Capabilities

### New Capabilities
- `price-adjustment`: 价格复权转换能力——从数据库加载 adj_factor，按用户选择的模式（qfq/hfq/none）转换信号计算用的 OHLCV 价格；成交执行保持 raw 价格

### Modified Capabilities
（无现有 spec 需要修改）

## Impact

- **后端数据层**: `pg_provider.py` — SQL 查询需 SELECT adj_factor 列
- **后端引擎入口**: `experiment_runner.py` — 在 history 加载后应用复权转换
- **后端引擎**: `portfolio_simulator_strict.py` — 需要同时持有信号价格（复权）和成交价格（raw），或在入口统一转换后传入
- **前端 JS**: `backtest_v2.js` — 读取 wbPriceAdj 控件值，写入 configDraft 和 runPayload
- **API 层**: `backtest_v2.py` — BacktestV2ExperimentRequest 增加 price_adj 字段
- **产物**: run_meta.json 增加 price_adj_mode 字段
