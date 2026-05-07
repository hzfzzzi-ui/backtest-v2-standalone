# holding/exit fragility research A/B notes

## 结果摘要

- stock-only 基线实验：`exp_20260412_105050570_af76`
- holding/exit 实验：`exp_20260412_105734828_91f2`
- 因子源：`stock_lifecycle_fragility_real_mainline_s1_1226`
- 因子：`pre_profit_failure_context_risk`
- 动作：`exit_candidate`
- 插入层：`holding_exit`

## A/B 结果

- baseline：`CAGR 16.38%`，`Sharpe 0.7671`，`MaxDD -32.48%`，`Calmar 0.5042`，`Trades 742`
- experiment：`CAGR 9.55%`，`Sharpe 0.5147`，`MaxDD -41.62%`，`Calmar 0.2294`，`Trades 632`

## 审计命中

- `portfolio_daily.csv`：
  - `enabled_days = 3448`
  - `gate_on_days = 1877`
  - `valid_days = 3448`
  - `days_with_matches = 96`
  - `days_with_high_risk = 33`
  - `days_with_exit_candidate = 33`
- `holding_exit_fragility_audit.csv`：
  - `fragility_high_risk_rows = 36`
  - `exit_candidate_rows = 37`
  - `actual_fragility_exit_rows = 32`

## 边界与结论

- 这轮结果说明：holding/exit hook 已经真正命中持仓并触发退出，不是“零作用面”的假实验。
- 这轮结论只代表当前插入点：`pre_profit_failure_context_risk -> holding_exit -> exit_candidate`。
- 当前结论是负向：该接法显著削弱收益并放大回撤，不建议推进为主线候选。
- 这轮结果不能外推成“lifecycle 研究线无效”，只能说明这版持仓层 `exit_candidate` 接法不成立。

## 后续修复：`watch` 必须严格 no-op

- 发现问题：`watch` 审计实验最初会改变真实交易路径，原因是 hook 进入点仍然参与了退出控制流。
- 修复方式：先按原有退出链生成正常 `reason`，再附加 fragility 审计；只有 `exit_candidate` 才允许在“原本没有退出理由”时补一个退出理由。
- 修复后 `watch` A/B：
  - baseline：`exp_20260412_123252255_20d7`
  - watch：`exp_20260412_124011334_681c`
  - 绩效完全一致：`CAGR 16.38%`，`Sharpe 0.7671`，`MaxDD -32.48%`，`Calmar 0.5042`，`Trades 742`
- 修复后 `watch` 审计命中：
  - `enabled_days = 3448`
  - `gate_on_days = 1877`
  - `days_with_matches = 303`
  - `days_with_high_risk = 150`
  - `days_with_watch = 150`
  - `actual_fragility_exit_rows = 0`

结论补充：

- `watch` 现在可以作为可靠的 research-only 审计面使用。
- 后续如果继续研究持仓层 lifecycle 因子，应先用 `watch` 观察命中对象，再决定是否尝试更轻的动作映射。
