## 1. Config 层

- [x] 1.1 在 `models.py` 新增 `MarketFilterConfig` dataclass（enabled, slope_window, bull_multiplier, light_multiplier, ema_light_fast, ema_light_slow）
- [x] 1.2 在 `BacktestConfig` 中新增 `market_filter: MarketFilterConfig` 字段（默认值）
- [x] 1.3 在 `loader.py` 中添加 `MarketFilterConfig` 加载逻辑

## 2. precompute 阶段 — MA200 四态计算

- [x] 2.1 在 `regime_router_signal_provider.py` 的 `precompute()` 中计算 benchmark MA200 slope（差分法，window=slope_window）
- [x] 2.2 计算 benchmark MA20、MA60、20日最高收盘价、60日最高价（用于过渡态入场条件）
- [x] 2.3 构建 `_market_state[T]` 数组（int8: 0=BULL, 1=TRANS_DOWN, 2=TRANS_UP, 3=BEAR）
- [x] 2.4 构建过渡态 entry_signal 布尔数组：条件 A（TRANS_DOWN）和条件 B（TRANS_UP）
- [x] 2.5 构建 `_trade_mode[T]` 数组（int8: 0=TREND_MAIN, 1=TREND_LIGHT, 2=NO_TRADE）
- [x] 2.6 计算 EMA5/20 信号矩阵 `_ema_light_buy_ok[T,N]`、`_ema_light_sell_ok[T,N]`、`_ema_light_cand_idx`

## 3. day_signals 分发逻辑改造

- [x] 3.1 在 `day_signals()` 中新增 trade_mode 三态分发逻辑（替代现有 regime_on 二值分发，仅当 market_filter 启用时）
- [x] 3.2 新增 `_day_signals_light()` 方法 — EMA5/20 买卖信号生成（结构仿 `_day_signals_trend()`）
- [x] 3.3 新增 `_day_signals_exits_only()` 方法 — NO_TRADE 模式仅处理退出规则
- [x] 3.4 在 Signal meta 中写入 market_state、trade_mode 字段
- [x] 3.5 新增市场状态分布计数器（market_state_bull_days 等 7 个），写入 metrics

## 4. risk_budget trend_multiplier 联动

- [x] 4.1 在 `portfolio_simulator_strict.py` 的 `_run_unified_loop()` 中，从 DaySignals.diagnostics 读取 trade_mode
- [x] 4.2 当 market_filter 启用时，用 trade_mode 动态设置 trend_multiplier（MAIN=bull_mult, LIGHT=light_mult, NO_TRADE=0）
- [x] 4.3 在 daily_row 中写入 `market_state` 和 `trade_mode` 字段

## 5. API / 实验透传

- [x] 5.1 在 `backtest_v2.py` / `_experiment_runner_api.py` 中解析前端传入的 market_filter 参数，构建 `MarketFilterConfig`
- [x] 5.2 在 `experiment_runner.py` 中透传 `MarketFilterConfig` 到引擎调用
- [x] 5.3 确保 `run_meta.json` 配置快照包含 market_filter 配置
- [x] 5.4 在 `backtest_v2_artifacts.py` 中将市场状态计数器写入 perf.json counters

## 6. 前端 UI 控件

- [x] 6.1 在 `index.html` 仓位风控区块中添加 "MA200 市场过滤" 控件组（开关 + slope_window + bull_mult + light_mult）
- [x] 6.2 在 `ui-controls.js` 中收集 market_filter 参数并发送到后端 API
- [x] 6.3 在 `ui-controls.js` 中实现 market_filter 参数回填（从已保存配置还原 UI 状态）

## 7. 图表市场状态蒙版

- [x] 7.1 在 `charts.js` 中实现 `MarketStateOverlay` LWC Series Primitive（MarketStateOverlay / MarketStatePaneView / MarketStatePaneRenderer 三个类）
- [x] 7.2 在 `renderNavChartLW()` 中接收 `opts.marketStates` 参数并挂载 overlay 到 LineSeries
- [x] 7.3 在 `renderDdChartLW()` 中同样挂载 overlay 到 BaselineSeries（双图表同步蒙版）
- [x] 7.4 在 `artifacts.js` 中从 portfolio_daily.csv 解析 market_state + trade_mode，转换为 `[{time, mode}]` 数组传入图表
- [x] 7.5 处理 market_filter 未启用时不挂载 overlay 的降级逻辑

## 8. 验证

- [x] 8.1 Docker rebuild + 运行回测，确认 market_filter.enabled=false 时行为与改动前一致
- [x] 8.2 启用 market_filter，确认 daily_row 包含 market_state / trade_mode 字段
- [ ] 8.3 确认图表显示红/绿/透明三色蒙版，与 daily_row 数据一致
- [x] 8.4 确认 BEAR 期间无买入交易，TREND_LIGHT 期间使用 EMA5/20 信号
- [x] 8.5 确认 perf.json counters 包含市场状态分布统计
