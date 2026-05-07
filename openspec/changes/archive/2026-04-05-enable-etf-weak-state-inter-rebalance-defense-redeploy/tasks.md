## 1. 执行合同与 explain 入口

- [x] 1.1 在 ETF execution path 中新增 weak-state inter-rebalance defense redeploy 触发合同与原因码，DoD：仅在 `TRANS_DOWN/RISK_OFF`、weak-state policy 激活且当前 posture 未满足时进入该路径；验证：静态代码链可定位 activation/reject 分支；风险：触发条件过宽会抬高不必要换手。
- [x] 1.2 将 inter-rebalance defense redeploy explain 字段接入 `run_meta/audit`，DoD：能区分“已激活并执行”“已满足防守姿态”“无 defense 候选”“被执行约束拒绝”；验证：运行产物可直接读取新原因码；风险：如果 explain 不足，后续无法判断失败原因。

## 2. 弱势执行路径实现

- [x] 2.1 在 ETF 非再平衡日执行链中实现 defense redeploy，DoD：当正式弱势 defense targets 存在且当前 live seats 未满足 posture 时，不再被 `AWAIT_BIWEEKLY_REBALANCE` 直接挡掉；验证：ETF standalone 回放中弱势非再平衡日出现 defense redeploy 或明确 reject 原因；风险：错误复用普通 ranking 会破坏单改动边界。
- [x] 2.2 保持 `BULL/TRANS_UP` 节奏与 stock/regime/combo 不变，DoD：代码 diff 只落在 ETF weak-state inter-rebalance 相关模块；验证：无 stock/regime/50_50 相关核心文件被改；风险：顺手改动主路径会破坏归因。

## 3. 回放验收

- [x] 3.1 用 ETF standalone 做首轮回放，DoD：弱势非再平衡日不再同时出现 `AWAIT_BIWEEKLY_REBALANCE + NO_SELECTED_ORDERS` 的主失败形态；验证：给出改前改后原因码与 posture 对比；风险：若只看总收益，可能掩盖执行链是否真的修通。
- [x] 3.2 用 `A_STOCK_ETF_V1` 做组合复核，DoD：组合层保留本轮单改动可归因，优先观察 Sharpe/Calmar/MaxDD 与弱势 explain 变化；验证：给出改前改后指标与弱势状态持仓对比；风险：若组合指标变化来自别的路径，研究结论不成立。
