## Why

全周期所有股票买入样本显示，`r2_60`、`slope60`、`ret60_vol_adj / ret60_dd_adj` 对后续收益和亏损尾部有更稳定的解释力，且比固定短期涨幅阈值更不容易过拟合。下一步需要验证这些趋势质量因子能否作为可执行的股票腿软排序/软降权，而不是继续扩大硬 veto 规则。

## What Changes

- 新增一轮研究专用的趋势质量软评分 AB。
- 候选方案只允许使用入场前可得的朴素趋势质量因子：
  - `r2_60`
  - `slope60`
  - `ret60_vol_adj`
  - `ret60_dd_adj`
- 首轮实现只做软排序或仓位折扣，不做硬拦截。
- 保持股票池、PIT 成分、交易时点、退出逻辑、成本、账户/NAV 计算不变。
- 先跑 `2016-2026` 主窗口；若主窗口可解释，再跑 `2012-2017` 硬门槛和 `2012-2026` 全周期审计。
- 输出 AB 对比、因子分桶、交易数、回撤、CAGR、Sharpe、Calmar、现金不足次数和 reason code 差异。

## Capabilities

### New Capabilities

- `trend-quality-soft-score-ab`: 定义股票腿趋势质量软评分 AB 的研究边界、输入因子、执行纪律和验收口径。

### Modified Capabilities

- 无。

## Impact

- Source:
  - `backend/core/strategies/breakout_trend.py`
  - `backend/core/strategies/registry.py`
  - `backend/core/engine_vector/breakout_provider_models.py`
  - `backend/core/engine_vector/breakout_provider_precompute.py`
  - `backend/core/engine_vector/breakout_signal_provider.py`
  - `backend/core/engine_vector/multifactor_rank.py`
  - `backend/research/*` 或 `backend/scripts/*` 中的研究执行/汇总脚本
- Runtime artifacts:
  - `outputs/experiments/*`
  - `outputs/analysis/trend_quality_soft_score_ab_*`
- Tests:
  - 配置关闭时行为等价
  - 开启时 intended diff 只包含趋势质量软评分字段
  - AB 输出包含三窗口关键指标和可回滚说明
