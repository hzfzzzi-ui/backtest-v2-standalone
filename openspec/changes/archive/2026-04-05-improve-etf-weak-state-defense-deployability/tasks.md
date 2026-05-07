## 1. 合同与配置入口

- [x] 1.1 在 ETF sleeve 配置层新增弱势承接 policy 配置与 formal defense candidate 定义，DoD：`TRANS_DOWN/RISK_OFF` 的 policy 能被单一入口解析且不改 stock/regime 配置；验证：静态配置编译通过并能在 runtime snapshot 中看到弱势 policy；风险：防守资产池定义过宽会演化为 ETF 池扩张。
- [x] 1.2 将 ETF weak-state policy 接入 runtime 编译真相，DoD：编译结果只从正式 policy 生成弱势承接输入；验证：`run_config/run_meta` 可追溯弱势 policy 来源；风险：若仍残留隐式 fallback，会导致结果不可归因。

## 2. 弱势部署实现

- [x] 2.1 在 ETF sleeve 运行路径中实现 `TRANS_DOWN/RISK_OFF` 的防守资产优先级与 deployability floor，DoD：存在可交易防守资产且目标暴露大于零时至少形成 1 个可执行 defense seat；验证：ETF standalone 回放中不再出现“有目标暴露但 `effective_max_positions=0`”的主失败形态；风险：错误放宽 slot/cap 会把防守实现成风险暴露抬升。
- [x] 2.2 保持 `BULL/TRANS_UP` 进攻段逻辑不变并隔离 stock 腿，DoD：本次实现不修改 stock sleeve、combo 配比与 regime framework；验证：代码 diff 只落在 ETF weak-state 相关模块；风险：顺手改动主路径会破坏单改动归因。

## 3. 审计与验收

- [x] 3.1 为弱势部署输出可审计解释字段与原因码，DoD：产物能区分“有可交易防守资产但被部署约束压零”和“无可交易防守资产”；验证：`run_meta` / explain surface 可直接读出弱势部署归因；风险：如果解释字段不足，后续无法判断失败来自资产池还是预算约束。
- [x] 3.2 用 `A_STOCK_ETF_V1` 和 ETF standalone 进行单改动回放验收，DoD：弱势阶段承接可落地，且优先观察 Sharpe/Calmar/MaxDD 是否改善而不是只看 CAGR；验证：给出改前改后指标、弱势状态持仓与原因码对比；风险：若同时调整多个变量，结果将失去研究价值。
