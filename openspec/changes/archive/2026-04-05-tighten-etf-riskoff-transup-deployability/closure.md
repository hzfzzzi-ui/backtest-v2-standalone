# 关停说明

## 结论

`tighten-etf-riskoff-transup-deployability` 当前未达到验收阈值，决定关停，不进入正式主线，不同步主 spec。

## 事实

- 当前验收门槛要求：`BULL / TRANS_UP` 的目标暴露与实际暴露偏差 `<= 0.10`
- 当前任务 `3.2` 未完成
- 当前 change 自带结论明确写出 acceptance threshold 未达成
- 最近一次记录实验：`exp_20260404_123303975_16d5`
- 记录值：
  - `BULL` 平均 gap `0.2252`
  - `TRANS_UP` 平均 gap `0.8438`

## 判断

- 这条线当前不是“差最后一点验证”，而是验收标准实质未达标
- 继续把它保留为 active change 只会制造“仍在推进”的假象
- 正确处理是：保留历史记录，明确标注为“已关停，不采纳”

## 处理方式

- 不同步主 spec
- 不伪造完成态
- 归档保存 proposal / design / tasks / specs，作为失败研究记录
