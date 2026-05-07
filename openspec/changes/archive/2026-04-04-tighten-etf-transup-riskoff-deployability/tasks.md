## 1. OpenSpec 与边界收口

- [x] 1.1 完成 `tighten-etf-transup-riskoff-deployability` 的 proposal/design/spec，并通过 `openspec validate`。DoD: change 至少达到 apply-ready；验证: `openspec validate tighten-etf-transup-riskoff-deployability --type change --strict`；风险: 误把 formal ETF stabilizer 口径一起改掉。

## 2. Contract 与执行路径实现

- [x] 2.1 修改 ETF contract，使 standalone mainline 在 `RISK_OFF` 下的正目标暴露生成非零 deployability，并保留可审计 reason_code。DoD: contract/unit test 明确覆盖 `RISK_OFF` 正 target 不再变成零 pace；验证: `pytest tests/unit/test_etf_beta_contract.py -q`；风险: `RISK_OFF` 承接逻辑与现有 fallback/defense 语义冲突。
- [x] 2.2 修改 ETF provider，使 standalone mainline 在 `TRANS_UP` 支持持续 recovery fill，在 `BULL/TRANS_UP` 支持非 rebalance gap-fill。DoD: provider test 能看到新的 execution path 与 reason_code，且不会污染 formal path；验证: `pytest tests/unit/test_cn_etf_beta_signal_provider.py -q`；风险: gap-fill 误触发成高频重平衡。
- [x] 2.3 收口 accounting/audit 证据链，确保 `BULL/TRANS_UP` 的 target、actual、pace gap 和 execution path 可以直接比较。DoD: accounting/audit 测试通过且研究产物能读出摘要；验证: `pytest tests/unit/test_bridge_adapter_accounting.py -q`；风险: 只改了行为，没补足可解释证据。

## 3. 回测迭代与结果核验

- [x] 3.1 运行 `etf/cn_broad_based_research_mainline_r1` 在 `2012-01-01` 到 `2026-03-24` 的回测并读取 `BULL/TRANS_UP` 偏差摘要。DoD: 生成新的实验目录与标准产物；验证: `perf.json`、`run_meta.json`、`audit.json` 可读；风险: 本机 DB host 解析失败导致需要继续走容器执行。
- [x] 3.2 若 `BULL` 或 `TRANS_UP` 的目标与实际暴露偏差仍大于 `10%`，继续在本 change 范围内迭代 contract/provider，直到达标或明确证明当前边界不可达。DoD: 最终结果说明包含“是否达标、为何达标/未达标、风险与回退”；验证: 直接引用最新实验产物；风险: 为追指标而偷偷改到资产池、study 或 formal 路径。
