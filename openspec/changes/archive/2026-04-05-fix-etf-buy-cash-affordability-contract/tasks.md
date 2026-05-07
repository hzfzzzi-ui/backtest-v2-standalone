## 1. 合同收口

- [x] 1.1 在 `order_sizing.py` / `execution_orders.py` 实现 fill 等价 BUY affordability 计算，并按 `lot_size` 裁剪到最大可负担数量
- [x] 1.2 保持 `fill_accounting.py` 的真实扣现金逻辑不变，只让 planning 与 fill 的现金口径收敛

## 2. 可观测性

- [x] 2.1 在 `daily/accounting` 与 `execution_lineage` 中补齐 planning `SKIP_NO_CASH` 与 fill `INSUFFICIENT_CASH` 的分层统计
- [x] 2.2 补充 ETF provider / execution kernel / fill accounting 回归测试，锁定“可负担 BUY 不再次日整单失败”的合同

## 3. 长窗回归

- [x] 3.1 重跑 ETF 单腿 `2012-2026` 回测，比对 execution lineage 的 `scheduled_count / filled_count / rejected_count`、`BULL / TRANS_UP` gap 与绩效变化
- [x] 3.2 以最小范围补一个 A 股基线 smoke，确认通用 BUY affordability 合同未引入明显非 ETF 回归
