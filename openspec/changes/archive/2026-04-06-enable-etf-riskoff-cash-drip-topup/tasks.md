## 1. RISK_OFF cash-drip 执行合同与可观测性

- [x] 1.1 在 ETF 弱势执行合同中新增 `RISK_OFF cash-drip top-up` 入口条件与必要配置透传；DoD：`RISK_OFF` 下仅当存在目标缺口、存在可用现金且满足最小可执行单位时才进入 drip 分支；验证：ETF standalone 回放中 formal/research explain 可见该分支已参与评估；风险：若条件过宽会把普通弱势日误放大成频繁交易。
- [x] 1.2 为 `RISK_OFF cash-drip top-up` 增加专属 explain 与原因码；DoD：至少能区分“已执行 drip top-up”“现金不足最小单位”“目标已满足无需补仓”“被硬约束阻断”；验证：`run_meta.json` 与 execution explain 中出现新原因码且不再只剩笼统 `execution_constraint`；风险：原因码粒度不足会导致下一轮无法继续收缩问题。

## 2. RISK_OFF cash-drip 执行路径实现

- [x] 2.1 在 ETF execution path 中实现 `RISK_OFF` 小额补仓逻辑，改用“最小可执行单位 + 可用现金”而不是“大 deploy gap 门槛”；DoD：只要现金足够买入最小单位，就允许一次小额 top-up，不要求一次补满 deploy gap；验证：ETF standalone 回放里 `RISK_OFF` 不再被 deploy gap 直接压成无单；风险：若 clip 逻辑错误，可能导致过度碎单或异常换手。
- [x] 2.2 按“债优先、核心宽基次之”落地 `RISK_OFF` drip 顺序，并保持 `TRANS_DOWN`、target map、stock、regime、组合 `50/50` 全部不变；DoD：`RISK_OFF` 下优先补 `511010.SH`，其次才补 `510300.SH`，且其他状态与模块行为无漂移；验证：对比改前改后 explain / perf，只有 `RISK_OFF` 执行链与原因码发生变化；风险：若误碰其他状态路径，会破坏本轮单改动归因。

## 3. 回放验收与风险复核

- [ ] 3.1 完成 ETF standalone 回放验收；DoD：确认 `RISK_OFF` 非零持仓率提升或 `REJECT_EXECUTION_CONSTRAINT` 明显下降，并能从 explain 中看到 drip top-up 的执行/拒绝归因；验证：对比 `perf.json`、`run_meta.json`、`portfolio_daily.csv`；风险：若行为仍无变化，说明主阻塞在更底层 affordability / lot 约束。
- [ ] 3.2 完成 `A_STOCK_ETF_V1` 组合回放复核；DoD：确认弱势 ETF 承接行为更符合直觉，且组合 `MaxDD`、`Calmar`、换手没有明显恶化；验证：对比组合 `perf.json`、`run_meta.json` 与 ETF component 实验；风险：若弱势补仓改善但组合风险明显变差，则本轮方案不应归档。

