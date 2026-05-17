## Why

D6 可见性审计显示，D5 半卖后的部分“卖早/修复”样本其实已经重新进入原始入场候选，但 provider 层已持仓过滤使它们无法进入候选规划和执行。现在需要用正式 AB 验证 `restore_candidate` 语义是否能改善股票腿回撤/收益，而不是继续凭逐笔样本推断。

## What Changes

- 新增研究专用 `restore_candidate` AB：当 D5 半卖后仍持有半仓，且同一标的重新进入原始入场候选时，允许生成恢复候选。
- 恢复买入只补足到正常目标仓位，不允许超过原本单票预算。
- 恢复候选必须继续经过同一 runtime 的可交易、排序、现金/lot 和执行检查。
- 新增三窗口 combo study，用同一 V3 combo 模板对比 B0、D5 immediate、D5 immediate + restore。
- 输出 restore 触发数、成交数、候选层拒绝原因和 same-window 绩效对比。
- 不提升 baseline，不改变股票池、ETF 池、排序主因子、D5 判定阈值或 combo NAV 真相。

## Capabilities

### New Capabilities
- `d6-restore-candidate-ab`: 研究专用 D6 restore_candidate AB 合同，覆盖 restore 信号生成、仓位恢复约束、候选/执行审计和 same-window 结论。

### Modified Capabilities
- None.

## Impact

- Source:
  - `backend/core/strategies/breakout_trend.py`
  - `backend/core/strategies/registry.py`
  - `backend/core/engine_vector/breakout_provider_models.py`
  - `backend/core/engine_vector/breakout_signal_provider.py`
  - `backend/core/engine_vector/breakout_provider_day_signals.py`
  - `backend/core/portfolio/candidate_plan.py`
  - `backend/core/portfolio/execution_orders.py`
  - `backend/core/engine_vector/strict_runtime_breakout.py`
  - `backend/core/stage_pipeline/adapters/fill_accounting.py`
  - `backend/research/cn_stock_etf_stock_rule_combo_ab_study.py`
  - `research/studies/cn_stock_etf/cn_stock_etf_d6_restore_candidate_ab_v1.study.yaml`
  - focused unit tests
- Runtime artifacts:
  - new `outputs/experiments/*`
  - new `outputs/studies/cn_stock_etf/cn_stock_etf_d6_restore_candidate_ab_v1/*`
  - updated study journal round
