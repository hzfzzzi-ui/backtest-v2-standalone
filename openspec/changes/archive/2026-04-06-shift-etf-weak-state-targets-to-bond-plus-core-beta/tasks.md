## 1. 弱势目标合同与默认配置

- [x] 1.1 新增 ETF 弱势“债加核心宽基”policy 配置与默认值，DoD：正式配置可表达 `RISK_OFF=511010 70% + 510300 30%`、`TRANS_DOWN=511010 55% + 510300 45%`；验证：静态代码链可定位默认配置与归一化入口；风险：若配置入口不单一，会再次造成弱势目标漂移。
- [x] 1.2 将新 policy 接入 ETF formal/research explain，DoD：运行产物可直接读出弱势目标映射，不再需要依赖外部推断；验证：静态代码链可定位 formal/research view 的输出字段；风险：如果 explain 不完整，后续无法判断弱势目标是否真的生效。

## 2. ETF 弱势目标映射实现

- [x] 2.1 将 `RISK_OFF` 的正式目标切到 `511010.SH 70% + 510300.SH 30%`，DoD：弱势正式 target map 不再包含黄金，且总暴露不变；验证：静态代码链可定位 `RISK_OFF` formal targets 的生成位置；风险：若顺手改到总暴露，会破坏单改动归因。
- [x] 2.2 将 `TRANS_DOWN` 的正式目标切到 `511010.SH 55% + 510300.SH 45%`，DoD：`TRANS_DOWN` 比 `RISK_OFF` 更积极但仍保持债为主；验证：静态代码链可定位 `TRANS_DOWN` target map 的生成位置；风险：若比例过于激进，会把本轮研究扩成风险预算抬升。
- [x] 2.3 保持 stock/regime/combo/execution constraint 不变，DoD：代码 diff 只落在 ETF 弱势目标合同与目标映射相关模块；验证：无 stock、regime、50_50、execution-constraint 核心文件被改；风险：顺手改动主路径会让结果无法归因。

## 3. 回放验收

- [ ] 3.1 用 ETF standalone 回放验证弱势目标结构，DoD：`RISK_OFF` 与 `TRANS_DOWN` 的 formal targets 变成债加核心宽基，且弱势非零持仓率高于当前纯防守版本；验证：给出改前改后 formal targets、原因码与弱势状态持仓对比；风险：若只看收益，可能掩盖弱势仓位行为仍不符合直觉。
- [ ] 3.2 用 `A_STOCK_ETF_V1` 做组合复核，DoD：组合层保留本轮单改动可归因，优先观察弱势状态持仓行为、MaxDD、Calmar 与换手变化；验证：给出改前改后指标与弱势状态资产构成对比；风险：若组合变化来自其他路径，则本轮研究结论不成立。
