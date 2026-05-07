## 结果结论

- `bull_only_tiebreak` 在当前股票腿基线 A/B 中与 baseline 绩效完全一致：`CAGR / Sharpe / MaxDD / Calmar / Trades` 全部相同。
- 这次不是负向 graft，而是“几乎没有实际作用面”。
- 因子结论应收紧为：`monthly_divergence_rate` 仍是研究层正向候选，但这版 `BULL-only tiebreak` 接法没有形成有效策略差异。

## 关键证据

- baseline: `exp_20260411_144806303_c0d6`
- experiment: `exp_20260411_145327086_aeef`
- A/B 摘要: `outputs/ops/moneyflow_bull_tiebreak_ab/ab_results.json`
- runtime 结果: `outputs/ops/moneyflow_bull_tiebreak_ab/runtime_results.json`
- PIT 恢复摘要: `outputs/ops/moneyflow_bull_tiebreak_ab/restore_csi800_formal_history_summary.json`

## 机制解释

- `portfolio_candidates.csv` 证明 overlay 在候选层真实启用，`overlay_gate_on=True` 的候选行很多。
- 但 moneyflow score 非空的候选仅 `598` 行，覆盖 `283` 个交易日。
- 在这些非空候选里，按 `mf_score` 真正出现并列的 tie group 只有 `1` 组、仅 `1` 个交易日。
- 因此 `tiebreak` 几乎没有机会改变最终候选顺序，导致整条交易路径与 baseline 一致。

## 已知限制

- `portfolio_daily.csv` 当前没有把 `moneyflow_overlay_bull_only / bull_gate_on / bull_suppressed` 三个新诊断字段稳定落出；候选级 CSV 有 `overlay_gate_on`，但日级聚合面还不完整。
- 因为本次绩效完全一致，当前不需要继续把这版接法推进到组合层。

## 回退

- 代码最小回退：
  - `backend/core/portfolio/candidate_plan.py`
  - `backend/core/portfolio/portfolio_runtime.py`
  - `backend/core/engine_vector/strict_runtime_breakout.py`
  - `tests/unit/test_multi_alpha_order_planning.py`
- OpenSpec 回退：删除本 change 目录。
