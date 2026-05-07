## 1. Spec 与合同收口
- [x] 1.1 完成 `tighten-etf-riskoff-transup-deployability` 的 proposal/design/specs 并通过 `openspec validate`。
- [x] 1.2 为 standalone mainline 定义 `TRANS_UP / RISK_OFF` 的部署合同分支。

## 2. Provider 与审计实现
- [x] 2.1 在 provider 中实现 `RISK_OFF / TRANS_UP` 的 `inter_rebalance_deploy` 路径，并仅在该路径下允许 held symbol top-up。
- [x] 2.2 保持 accounting/audit 证据链完整。

## 3. 回测与迭代
- [x] 3.1 运行 `etf/cn_broad_based_research_mainline_r1` 的 `2012-01-01` 到 `2026-03-24` 回测。
- [ ] 3.2 以 `BULL / TRANS_UP` 的目标暴露与实际暴露偏差 `<= 0.10` 为验收，未达标则继续最小迭代。

## 当前结论
- 最新实跑：`exp_20260404_123303975_16d5`
- 当前结果：
  - `BULL` 平均 target `1.0`，平均 actual `0.7748`，平均 gap `0.2252`
  - `TRANS_UP` 平均 target `0.9`，平均 actual `0.0656`，平均 gap `0.8438`
- 判断：合同、provider 路径、held top-up 与审计证据链已经打通，但验收阈值仍未达成；剩余主瓶颈已从 contract / timing gap 转为 `execution_residual_gap`
