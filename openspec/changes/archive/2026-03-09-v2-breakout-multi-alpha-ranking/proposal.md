## Why

当前 `breakout_trend` 在锁定 baseline 下已经证明“单一突破 alpha 有效但过窄”，主要问题是候选稀疏、平均持仓偏低、收益过度依赖少数趋势年份。现在需要在不改成本、股票池、执行口径和 `t+1` 契约的前提下，为同一组合框架补充可审计的新 alpha 来源，并把排序层升级成统一可解释的多分数排序。

## What Changes

- 为 `breakout_trend` 增加默认关闭的 `pullback_trend` 候选分支，与 breakout 并行产出候选信号。
- 在候选排序层增加默认关闭的残差相对强弱分数、行业强度分数、量价质量分数和综合分。
- 保持现有组合层与下单框架不变，仅在候选构建和候选排序阶段做增量接线。
- 新增 PIT-safe 的股票-行业日级映射加载，禁止继续使用“最新行业记录”回看历史。
- 新增候选与排序诊断产物，包括 `candidate_signals.csv`、`alpha_funnel.csv`、`score_diagnostics.csv`、`ab_summary.csv`。
- 新增三阶段最小实验脚本：Phase 1 仅加 pullback，Phase 2 再加 residual ranking，Phase 3 再加行业+量价综合排序。

## Capabilities

### New Capabilities
- `multi-alpha-candidate-ranking`: 在 breakout 主路径中并行支持 pullback alpha，并为 breakout/pullback 候选提供统一排序与选股。
- `alpha-candidate-diagnostics`: 输出候选来源、分数、筛选漏斗和阶段 AB 对比，保证候选与入选原因可追踪。
- `pit-sector-membership-matrix`: 为行业强度与行业相对强弱提供按交易日可见的 PIT-safe 股票-行业映射矩阵。

### Modified Capabilities

## Impact

- 影响代码：
  - `backend/core/engine_vector/breakout_signal_provider.py`
  - `backend/core/portfolio/portfolio_builder.py`
  - `backend/core/tools/experiment_runner.py`
  - `backend/core/data/provider.py`
  - `backend/core/data/pg_provider.py`
  - `backend/core/data/cached_provider.py`
  - `backend/api/endpoints/backtest_v2_artifacts.py`
  - 新增研究脚本与汇总脚本
- 影响产物：
  - 现有 `perf.json / nav.csv / portfolio_trades.csv / run_meta.json` 保持不变
  - 新增候选与打分诊断 csv
- 影响审计：
  - 需要新增行业映射时点审计
  - 需要新增横截面排序同日样本审计
