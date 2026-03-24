## 1. Regime Contract 收口

- [x] 1.1 新增或收敛 `market_regime_engine` facade，统一输出 canonical 五状态、coarse 状态、confidence、transition reason、reason codes 和 feature availability。  
  DoD：引擎层存在唯一正式 payload 构造入口，且五状态被定义为唯一正式真相源。
- [x] 1.2 把 block 级与 domain 级归因字段收口到正式 regime payload，包括 `block_scores.*`、`subscores.technical`、`subscores.sentiment`、`subscores.macro_global`。  
  DoD：下游不再依赖 audit 后处理补全核心归因字段。
- [x] 1.3 为 regime payload 增加 `state_stability_metrics` 和 `manual_override` 正式结构。  
  DoD：低置信度抑制、最短持续期抑制、cooldown、override 生效都能在 payload 中被识别。

## 2. Governor 与 Audit 消费统一

- [x] 2.1 调整 `cn-a-portfolio-governor` 相关实现，只消费正式 regime payload，不再自行推断 canonical 状态或 override 语义。  
  DoD：Governor 摘要引用 `base/effective_state`、`risk_budget_multiplier`、`defense_bias`、`reason_codes`。
- [x] 2.2 调整 `cn-a-attribution-audit`，统一记录 state/budget/sleeve/manual override 证据链。  
  DoD：Attribution audit 能回答状态来源、预算来源、干预来源。
- [x] 2.3 调整 `backtest-research-audit`，让 Governed A 股实验引用统一 regime/attribution 证据链。  
  DoD：Research audit 不再通过结果字段自行猜测状态和预算原因。

## 3. Snapshot 与前端边界收口

- [x] 3.1 调整 `results-workbench-snapshot-boundary` 对应实现，把 Governed A 股最小 regime/governor 摘要写入 snapshot。  
  DoD：snapshot 可直接暴露状态、预算、reason code、override 摘要。
- [x] 3.2 为结果工作台补最小消费链路，确保前端不再以 `market_state` / `trade_mode` 推断 Governed A 股状态语义。  
  DoD：前端最少能读取新的 snapshot 摘要字段。

## 4. 回归、诊断与回退

- [x] 4.1 为 regime/governor/attribution/snapshot 增加最小回归测试集。  
  DoD：新增测试覆盖 canonical 状态映射、双轨 override、Governor 消费、snapshot 摘要。
- [x] 4.2 运行 A 股股票主线最小回归，确认 contract 收口不引入未解释行为漂移。  
  DoD：核心收益、回撤、交易数与基线差异可解释或为零。  
  说明：首次 rerun 漂移由 `baseline_regression_check` 的 `workbench_config` 请求源退化导致，修复后 `portfolio_daily / perf / nav / run_meta` 均回到 `PASS`；剩余 diff 已确认为 additive enrichment，不属于未解释行为漂移。
- [x] 4.3 补实现说明与回退路径，明确如何关闭新 regime facade、如何回退 snapshot 暴露面、如何恢复旧消费链路。  
  DoD：change 内有实现说明文档，且回退路径按模块分层清晰。
