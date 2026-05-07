## 1. 诊断合同

- [x] 1.1 扩展 formal ETF stabilizer 的日级诊断字段，补齐 `approved target -> floor/overlay -> pace -> execution path -> actual` 链条。DoD: `portfolio_daily.csv` 能直接读出 `BULL/TRANS_UP` 的 pace 诊断链；验证: `tests/unit/test_bridge_adapter_accounting.py` 与 `tests/unit/test_experiment_runner_daily_schema.py`；风险: 不得再引入第二套 target 真相。
- [x] 1.2 扩展 ETF 订单元数据与 provider 证据，让 `BULL/TRANS_UP` 的缺口归因能回到 execution path 和 reason code。DoD: `orders.csv` 或等价元数据能回答“为什么 pace 没变成实际仓位”；验证: `tests/unit/test_cn_etf_beta_signal_provider.py`；风险: 不得把执行结果倒灌成合同。

## 2. 审计归因

- [x] 2.1 在 `research_audit` 中新增 `pace_policy_gap / rebalance_timing_gap / execution_residual_gap` 的 owner attribution。DoD: `audit.json` 能独立解释 `BULL` 与 `TRANS_UP` 的缺口来源；验证: `tests/unit/test_research_audit_contract.py`；风险: 不得把合同主动保守误判成执行缺陷。
- [x] 2.2 对 `BULL` 与 `TRANS_UP` 分别输出实验级摘要，而不是合并成单一 ETF underdeployment 结论。DoD: 审计与诊断摘要明确区分两种状态；验证: `tests/unit/test_research_audit_contract.py`；风险: 不得因聚合方式错误掩盖 `TRANS_UP` 的独特瓶颈。

## 3. 回归与研究结论

- [x] 3.1 补齐 contract/provider/accounting/audit/schema 相关回归测试。DoD: 受影响单测全部通过；验证: `pytest tests/unit/test_etf_beta_contract.py tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_bridge_adapter_accounting.py tests/unit/test_research_audit_contract.py tests/unit/test_experiment_runner_daily_schema.py -q`；风险: 不得引入 timing 或 accounting 回归。
- [x] 3.2 重跑正式 ETF 子实验并给出 `BULL/TRANS_UP` 的 bottleneck 对照摘要。DoD: 输出新实验中两种状态的 `target/floor/overlay/pace/actual/gap owner` 摘要；验证: 正式 ETF study 重跑与实验对照；风险: 必须明确这是诊断研究，不得误报为收益优化。
