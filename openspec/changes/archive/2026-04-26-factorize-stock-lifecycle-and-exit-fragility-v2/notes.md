# Notes

## Outcome

本 change 的 catalog、snapshot 与 study surface 已完成，且 real mainline 三窗口研究已经实际跑出：

- `1217` guardrail
- `1222` main
- `1226` audit

研究对象和三窗口定义已落在 [stock_lifecycle_fragility_real_mainline_s1.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/factors/stock_lifecycle_fragility_real_mainline_s1.study.yaml)。

## Evidence

三窗口 machine 分析产物：

- [1217 analysis.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/studies/factors/stock_lifecycle_fragility_real_mainline_s1/1217/B0_EQUAL/machine/analysis.json)
- [1222 analysis.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/studies/factors/stock_lifecycle_fragility_real_mainline_s1/1222/B0_EQUAL/machine/analysis.json)
- [1226 analysis.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/studies/factors/stock_lifecycle_fragility_real_mainline_s1/1226/B0_EQUAL/machine/analysis.json)

实现入口：

- [stock_lifecycle_fragility_study.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/research/stock_lifecycle_fragility_study.py)

## Boundary

这些结果当前仍是 `RESEARCH_ONLY`。它们用于解释 holding lifecycle / exit fragility 的风险分层和值得继续研究的 veto 方向，不构成“已证明应进入正式主线 runtime”。

## Research Summary

较值得继续观察的是：

- `early_fade_risk`
  - 在 `1222 / 1226` 的 `10d / 20d` 上，多次出现正向 `veto_top20_improvement`
- `pre_profit_failure_context_risk`
  - 在 `1222 / 1226` 的 `10d / 20d` 上，改善幅度相对更稳定
- `low10_exit_context_risk`
  - 在长窗口上存在弱正向改善，但幅度较小

当前不建议直接推进的有：

- `weak_carry_risk`
  - 三窗口没有形成稳定正向 veto 结论
- `break_floor_risk`
  - 当前更像解释性标签，未形成可用 veto 改善
- 等权 `factor_score`
  - 组合分数改善幅度弱，尚不足以当成正式主线候选

## Next Round

- 保持 `RESEARCH_ONLY` 边界
- 下一轮只建议把 `early_fade_risk` 与 `pre_profit_failure_context_risk` 做成更严格的 veto / conditional overlay A/B
- 不建议基于本次结果直接修改 stock mainline runtime 或 baseline
