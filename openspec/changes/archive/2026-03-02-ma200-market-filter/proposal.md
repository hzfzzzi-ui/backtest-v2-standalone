## Why

MA200 四象限分析表明，全部利润来自 BULL 象限（基准指数收盘价 > MA200 且 MA200 斜率为正），其余三个象限合计亏损约 2.8 万。当前 RegimeRouter 使用 MA60 做二值切换（趋势/均值回归），在熊市和结构不确认期仍允许 MR 交易，导致持续消耗本金。需要一个更高层级的市场状态过滤器来从根本上解决"错误市场环境下开仓"的问题，同时在图表上可视化市场状态以便研究验证。

## What Changes

- **新增 MA200 四态市场过滤器**：以基准指数 MA200 位置和斜率划分 BULL / TRANS_DOWN / TRANS_UP / BEAR 四种市场状态
- **新增交易模式映射**：BULL → TREND_MAIN（正常趋势），TRANSITION + 入场确认 → TREND_LIGHT（EMA5/20 轻趋势），其余 → NO_TRADE（仅退出）
- **完全废弃 MR 路径**：RegimeRouter 的"震荡态策略"槽位从 RSI Reversal 替换为 EMA Cross 轻趋势，不再产生任何 MR 买入信号
- **仓位系数联动 risk_budget**：TREND_MAIN multiplier=1.5, TREND_LIGHT=0.6, NO_TRADE=0，替代现有静态 `trend_multiplier=1.0`
- **图表市场状态蒙版**：在收益率&大盘 K 线图上用半透明色带标注市场状态——红色=趋势/小趋势（A股红涨），绿色=熊市（A股绿跌），透明=过渡无信号
- **daily_row 新增字段**：`market_state`（BULL/TRANS_DOWN/TRANS_UP/BEAR）、`trade_mode`（TREND_MAIN/TREND_LIGHT/NO_TRADE）

## Capabilities

### New Capabilities
- `ma200-market-state`: 基于基准指数 MA200 + 斜率的四态市场分类（BULL/TRANS_DOWN/TRANS_UP/BEAR）及对应交易模式映射
- `market-state-chart-overlay`: 在 LightweightCharts 收益率图表上绘制市场状态半透明色带蒙版

### Modified Capabilities
- `regime-router`: 废弃 MR 路径，震荡态策略槽位改为 EMA Cross 轻趋势；day_signals 分发逻辑从 regime_on 二值改为 trade_mode 三态
- `volatility-sizing`: trend_multiplier 从静态配置改为由 trade_mode 动态决定（TREND_MAIN=1.5, TREND_LIGHT=0.6, NO_TRADE=0）

## Impact

- **后端核心**：`regime_router_signal_provider.py`（precompute 新增 MA200/slope/MA20/MA60/breakout 矩阵 + EMA5/20 信号矩阵；day_signals 重写分发逻辑）、`portfolio_simulator_strict.py`（trend_multiplier 读取 trade_mode）
- **配置**：`models.py` 新增 `MarketFilterConfig`；`loader.py` 加载逻辑；`regime_router.py` strategy 配置
- **前端**：`charts.js`（新增 MarketStateOverlay LWC primitive）、`artifacts.js`（解析 market_state 数据传入图表）、`index.html`（MA200 过滤器参数控件）、`ui-controls.js`（参数收集/回填）
- **API**：`backtest_v2.py` / `_experiment_runner_api.py` 透传 MarketFilterConfig
- **产物协议**：daily_row 新增 `market_state` + `trade_mode` 字段；perf.json 新增市场状态分布统计计数器
