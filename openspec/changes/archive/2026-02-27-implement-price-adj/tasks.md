## 1. 数据层：加载 adj_factor

- [x] 1.1 修改 `pg_provider.py` 的 `load_ohlcv_daily()` — 在 SQL 查询列中增加 `adj_factor`，在 `_filter_existing_cols` 的期望列列表中添加 `"adj_factor"`。将返回 DataFrame 中 adj_factor 为 NaN 的行填充为 1.0。DoD: 返回的 DataFrame 包含 adj_factor 列且无 NaN。验证: Docker 内 python 脚本调用 load_ohlcv_daily 检查列名和 NaN 计数。

## 2. 复权转换函数

- [x] 2.1 新建 `backend/core/data/price_adjust.py`，实现 `apply_price_adjustment(history: pd.DataFrame, mode: str) -> pd.DataFrame` 纯函数。支持 "hfq"/"qfq"/"none" 三种模式。不修改原始 DataFrame（返回新 copy）。DoD: 三种模式均有正确输出，原 DataFrame 不变。验证: 单元测试用已知 adj_factor 验证转换结果。

## 3. experiment_runner 层集成

- [x] 3.1 修改 `experiment_runner.py` 的 `run_experiment()` — 在 `history = provider.load_ohlcv_daily(...)` 之后，读取 overrides 中的 `price_adj` 参数（默认 "hfq"），调用 `apply_price_adjustment(history, mode)` 生成 `signal_history`。保留原始 `history` 作为 `raw_history`。DoD: run_experiment 内有 signal_history 和 raw_history 两个变量。

- [x] 3.2 修改 `run_experiment()` — 将 `signal_history` 传给 `run_portfolio_backtest()` 的 `history` 参数，同时新增 `raw_history` 参数传入。将 `price_adj_mode` 和 adj_factor 统计信息写入返回字典。DoD: 返回 dict 中包含 price_adj_mode 字段。

## 4. 引擎层：双价格通道

- [x] 4.1 修改 `portfolio_builder.py` 的 `run_portfolio_backtest()` 签名 — 新增 `raw_history: pd.DataFrame | None = None` 参数，透传给 `run_vector_portfolio_backtest_strict()`。DoD: 编译通过，raw_history=None 时行为不变。

- [x] 4.2 修改 `portfolio_simulator_strict.py` 的 `run_vector_portfolio_backtest_strict()` 和 `_run_vector_portfolio_backtest_generic_signals()` 签名 — 新增 `raw_history: pd.DataFrame | None = None` 参数。当 raw_history 为 None 时，fallback 为 `history`（向后兼容）。DoD: 无 raw_history 时行为与改动前完全一致。

- [x] 4.3 修改引擎中 `open_idx` / `close_idx` 构建逻辑 — 改为从 `raw_history`（而非 `history`）构建，确保成交执行使用不复权价格。信号矩阵 `mx` 仍由 `history`（复权后）构建。DoD: open_idx 中的价格为不复权值。验证: 对比除权日的 open_idx 价格与数据库原始值一致。风险: 需要在两条路径（strict 和 generic_signals）中都修改。

## 5. API 层

- [x] 5.1 修改 `backtest_v2.py` 的 `BacktestV2ExperimentRequest` — 新增 `price_adj: str = "hfq"` 字段。在 overrides 构建时添加 `overrides["price_adj"] = body.price_adj`。DoD: API 接受 price_adj 参数并传入 experiment_runner。

## 6. 前端接通

- [x] 6.1 修改 `backtest_v2.js` 的 `buildConfigDraft()` — 读取 `wbPriceAdj` 控件值（select 或 segmented button），写入 `draft.universe.price_adj`。DoD: configDraft 中包含 price_adj 字段。

- [x] 6.2 修改 `backtest_v2.js` 的 `runPayloadFromDraft()` — 从 draft 中提取 `price_adj` 写入 payload 顶级字段。DoD: API 请求中包含 price_adj。

- [x] 6.3 修改 `backtest_v2.js` 的 `applyConfigToUI()` — 从 loaded config 中读取 price_adj 并回显到 wbPriceAdj 控件。DoD: 加载历史配置时控件状态正确。

## 7. 产物与可观测性

- [x] 7.1 修改 `backtest_v2_artifacts.py` — 在 run_meta 中写入 `price_adj_mode` 和 `adj_factor_stats`（min/max/null_count）。DoD: run_meta.json 包含 price_adj_mode 字段。验证: 运行回测后检查 outputs 目录下的 run_meta.json。

## 8. Docker 验证

- [x] 8.1 Docker rebuild 并运行端到端测试 — 用 hfq 模式跑一个含除权股票的回测，确认信号计算使用复权价，成交使用不复权价，run_meta 包含 price_adj_mode。DoD: 除权日前后的均线指标平滑（无跳空假信号），trades.csv 中 price 为不复权值。
