# 关停说明

## 结论

`enable-etf-riskoff-cash-drip-topup` 已完成实现，并已将当前有效的 `RISK_OFF cash-drip` 执行语义同步到主 spec，但未带来弱势持仓行为改善，不再保留为 active change。

## 事实

- 当前主线已支持：
  - `RISK_OFF cash-drip top-up`
  - 债优先、核心宽基次之
  - 单独的 activation / reject 原因码
- 最新回放显示：
  - 不再卡在 `AWAIT_BIWEEKLY_REBALANCE`
  - 不再主要表现为笼统 `execution_constraint`
  - 主失败原因已收敛为 `cash too small`
- ETF standalone 与组合层指标未发生实质变化

## 判断

- 该 change 的价值在于缩小问题边界，并把主失败原因定位到 cash / lot affordability
- 该 change 没有完成“改善弱势非零持仓率”的目标
- 后续若继续推进，应聚焦：
  - 状态切换时的现金释放
  - lot threshold / affordability

## 处理方式

- 同步主 spec
- 不继续保留 active 状态
- 归档保留 proposal / design / tasks / specs / closure，作为已实现但行为未达目标的研究记录
