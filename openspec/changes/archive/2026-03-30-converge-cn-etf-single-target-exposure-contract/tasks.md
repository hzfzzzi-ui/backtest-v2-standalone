## 1. 合同收敛

- [x] 1.1 收敛 [backend/core/config/etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py) 与 [backend/core/engine_vector/cn_etf_beta_signal_provider.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py) 的 ETF target 语义；DoD：formal Phase 1 只产出一套 notional `target_exposure`，且进入执行链的目标字段不再承载 `>1.0` 的 multiplier；验证：新增 contract/provider 单测覆盖 `BULL`、`TRANS_DOWN`、`RISK_OFF` 与越界 target；风险：误把 Governor multiplier 链彻底删坏，导致 boundary 证据缺失。
- [x] 1.2 收敛 [backend/core/portfolio/portfolio_runtime.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/portfolio/portfolio_runtime.py) 的 ETF order sizing 输入；DoD：BUY signal 只按统一 `target_exposure_per_symbol` sizing，不再旁路恢复旧预算；验证：执行层单测断言 BUY order value 与统一 target 对齐；风险：改变历史买入规模，导致 formal run 行为显著变化。

## 2. 产物与审计

- [x] 2.1 收敛 [backend/core/stage_pipeline/adapters/daily_accounting.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/adapters/daily_accounting.py) 与 ETF 诊断汇总输出；DoD：`portfolio_daily.csv`、`rebalance_day_summary.csv` 和相关 summary 对同一决策日回写一致的 ETF target；验证：回归测试对账同日 artifact 中的 ETF target 字段；风险：快照时点差异被误当成目标合同差异。
- [x] 2.2 收敛 [backend/core/audit/research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py) 的 ETF target 审计；DoD：`avg_target_exposure` 基于统一执行 target 统计，并在发现双口径时显式报 drift；验证：审计测试覆盖“同日 0.2 vs 1.8 冲突”与“一致 target”两类场景；风险：审计门槛过严导致旧实验大量转为 WARN/FAIL。

## 3. 回归与对照

- [x] 3.1 补齐 formal ETF target contract 回归；DoD：受影响的 contract/provider/runtime/audit 单测全部通过，且包含 `target_exposure <= 1.0` 的硬约束；验证：运行受影响 `pytest` 子集并保存结果；风险：测试只覆盖字段，不覆盖真实 artifact 对账。
- [x] 3.2 重跑 formal ETF study 并形成新旧对照；DoD：新实验中 orders、daily、summary、audit 的 ETF target 语义一致，并给出与 [exp_20260328_024314957_8f44](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260328_024314957_8f44) 的差异说明；验证：检查 `orders.csv`、`portfolio_daily.csv`、`rebalance_day_summary.csv`、`audit.json`；风险：target 合同修复后暴露出独立的 rebalance timing 问题。
- [x] 3.3 完成 OpenSpec 校验与回退说明；DoD：`openspec validate --changes "converge-cn-etf-single-target-exposure-contract"` 通过，并在实现总结中写清回退文件与验证命令；验证：执行 OpenSpec 校验；风险：spec 完整但实现范围偷偷扩大到 denominator 或收益优化。
