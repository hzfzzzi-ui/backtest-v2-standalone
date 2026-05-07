## Why

当前 ETF 独立主线已经确认存在新的主链断层：执行核会生成大量“已选中”的 BUY 订单，但这些订单在次日开盘 fill 阶段又大量被 `INSUFFICIENT_CASH` 拒绝。`exp_20260401_045408774_3961` 的 execution lineage 已显示 `805` 个 scheduled orders 里只有 `55` 个 filled、`750` 个 rejected，这使 `selected_count`、`after_cash_lot_count` 与真实成交能力脱节，直接放大了 `BULL / TRANS_UP` 的 under-deploy。

这个问题必须现在修，因为它已经不是策略收益讨论，而是执行合同本身不一致：执行核按 `qty * next_open` 判断“买得起”，fill 阶段却按 `open*(1+slip) + commission` 真实扣现金。只要这个口径不收敛，后续任何 ETF 优化都会继续被假阳性的 selected orders 污染。

## What Changes

- 对 BUY 订单建立统一的 `cash affordability` 合同，使执行核在 planning 阶段按 fill 等价口径评估现金可负担性，而不是只按毛金额判断。
- 当目标订单超出可负担现金时，执行核必须先按整手约束裁剪到可负担数量；若裁剪后不足一手，则在 planning 阶段直接拒绝，不再把注定次日失败的订单写入 scheduled orders。
- 增加最小诊断与审计口径，使 planning 阶段的 `SKIP_NO_CASH` 与 fill 阶段的 `INSUFFICIENT_CASH` 能被分层观察，便于验证改动是否真正消除了假阳性 selected orders。

## Capabilities

### New Capabilities

- `buy-cash-affordability-contract`: 定义 BUY 订单从 planning 到 fill 的统一现金可负担合同、整手裁剪规则与诊断边界。

### Modified Capabilities

- `cn-etf-beta-sleeve`: ETF 单腿运行时必须消费新的 BUY 现金可负担合同，避免 standalone deploy 继续产生次日必败订单。

## Impact

- 影响代码：`backend/core/portfolio/order_sizing.py`、`backend/core/portfolio/execution_orders.py`、`backend/core/stage_pipeline/adapters/fill_accounting.py`、`backend/core/stage_pipeline/adapters/daily_accounting.py`
- 影响审计：execution lineage、daily diagnostics、ETF `BULL / TRANS_UP` under-deploy 解释
- 影响测试：ETF provider / execution kernel / fill accounting / lineage 相关单测与 ETF 长窗回测验证
