## 1. ETF Contract Owner 收口

- [x] 1.1 新增 ETF contract owner 模块，统一承接 ETF beta 配置归一化与 canonical projection。
- [x] 1.2 将 provider、artifact finalize、research audit 切换为消费 canonical ETF contract projection，不再多层重复手工归一化。

## 2. 结果真相下沉

- [x] 2.1 为 research combo 与只读组合锚点补 canonical truth surface / snapshot，由后端直接返回 combo formal truth。
- [x] 2.2 下沉 regime / Governor / combo 语义，移除前端从 `dailyRows`、`market_state`、`trade_mode` 反推正式结果的活跃逻辑。

## 3. 前端 Owner Boundary 收紧

- [x] 3.1 收紧 `backtest_v2.js`、`ui-controls.js`、`artifacts.js` 的职责，只保留 bootstrap、bridge、chrome 与兼容提示。
- [x] 3.2 清理旧壳中的重复活跃 helper 与 owner 冲突函数，并补静态边界测试。

## 4. 回归与收口

- [x] 4.1 覆盖 ETF 结果页、research combo 页和 Governed A 股结果页的最小 smoke，确认 snapshot、audit 与 surface 真相一致。
- [x] 4.2 编写实现说明，明确影响模块、风险、验证与回退路径。
