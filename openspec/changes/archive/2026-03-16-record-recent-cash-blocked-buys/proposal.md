## Why

当前回测虽然已经会记录聚合级别的 `cash_skip_count`，但最近一次回测无法直接回答“最近一周哪些股票在拟买入时因资金不足被拦截”。这导致资金约束是否真实生效只能靠人工翻 `portfolio_daily` 和候选表猜测，既不利于审计，也不利于前端直接展示诊断结论。

## What Changes

- 为候选买入审计行补充资金拦截相关字段，包括拦截当日现金、估算买入股数、估算买入金额和估算价格。
- 新增 canonical artifact `cash_blocked_buys_recent.csv`，每次回测都落盘最近一周交易日内因资金不足被拦截的股票明细。
- 新增 `surface/cash_blocked_buys_recent` section，允许桌面端和诊断工具按统一结果面读取这份明细。
- 不修改执行时点、信号时点、成交口径或资金分配逻辑；只补充诊断输出。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `artifact-finalization-pipeline`: finalize pipeline 需要新增最近一周资金不足拦截买入明细 artifact，并保证空结果时也稳定落盘。
- `http-surface-boundary-split`: 实验 surface 需要新增 `cash_blocked_buys_recent` section，统一暴露最近一周资金不足拦截买入明细。

## Impact

- 影响代码：
  - `backend/core/portfolio/portfolio_runtime.py`
  - `backend/api/backtest_v2/protocol.py`
  - `backend/api/backtest_v2/artifacts_diagnostics.py`
  - `backend/api/backtest_v2/artifacts_finalize.py`
  - `backend/core/services/experiment_query_service.py`
- 影响产物：
  - `portfolio_candidates.csv` 会新增资金拦截诊断字段
  - 每个实验目录新增 `cash_blocked_buys_recent.csv`
- 不影响：
  - `baseline_V10.1` 的信号时点、成交时点、收益/回撤/交易数口径
