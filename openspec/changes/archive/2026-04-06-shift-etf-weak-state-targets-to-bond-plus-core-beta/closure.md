# 关停说明

## 结论

`shift-etf-weak-state-targets-to-bond-plus-core-beta` 已完成实现，并已将当前有效的目标结构同步到主 spec，但未观察到弱势持仓行为改善，不再保留为 active change。

## 事实

- 当前主线已采用：
  - `RISK_OFF` 债为主、少量核心宽基为辅
  - `TRANS_DOWN` 债为主的过渡结构
- 回放结果显示：
  - explain 与 target 结构已改变
  - ETF standalone 与组合层指标未发生实质变化
  - `RISK_OFF` 非零持仓率未改善

## 判断

- 该 change 证明“弱势目标结构”已进入主线真相
- 但未证明“仅改 target map 就能改善弱势行为”
- 后续问题已转移到更底层的 execution / cash / lot feasibility

## 处理方式

- 同步主 spec
- 不继续保留 active 状态
- 归档保留 proposal / design / tasks / specs / closure，作为已实现但行为未达目标的研究记录
