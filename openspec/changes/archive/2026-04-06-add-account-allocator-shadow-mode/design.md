## Overview

该 change 只新增账户层影子预算与 explain，不改变任何执行。

## Inputs

- 当前账户状态
- 当前 sleeve 实际预算
- 当前风险状态与库存摘要
- 执行约束摘要

## Outputs

- 建议 defense / core beta / alpha 预算
- 当前实际 budget snapshot
- suggested vs actual 的偏差原因
- 是否建议现金释放

## Non-Goals

- 不直接修改 stock / ETF 下单行为
- 不改变 `50/50` 现有运行逻辑
- 不引入新的 regime

## Verification Intent

成功标准不是收益变化，而是：
- 账户级 explain 可读
- 建议预算与当前预算的偏差可追溯
- 回测结果无漂移
