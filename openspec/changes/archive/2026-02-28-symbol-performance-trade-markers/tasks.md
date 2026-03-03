## 1. 后端口径与产物

- [x] 1.1 新增个股绩效聚合计算模块（快速口径：已平仓配对 + 未平仓末日收盘近似估值）【DoD: 生成每个 symbol 的 return_pct/max_drawdown/net_pnl/trades/unrealized_approx_pnl；验证: 本地样例回测后字段齐全；风险: 末日缺价回溯逻辑导致口径波动】
- [x] 1.2 在产物稳定化流程中写出 `symbol_performance.csv/json` 并登记 artifacts【DoD: manifest/artifacts 包含 symbol_performance；验证: `/api/backtest_v2/artifacts/read` 可读；风险: 老实验目录兼容】

## 2. 后端 API

- [x] 2.1 新增 `/api/backtest_v2/series/symbol` 接口（区间内返回个股归一化序列）【DoD: 输入 symbol/start/end 返回 points；验证: curl + 前端联调；风险: symbol 规范化（sh/sz 与 .SH/.SZ）】
- [x] 2.2 完善接口异常与空数据语义（404/empty/source 字段）【DoD: 错误可区分且前端可提示；验证: 不存在 symbol、停牌区间、DB 异常用例；风险: 与 benchmark 接口语义混淆】

## 3. 前端榜单与筛选

- [x] 3.1 在绩效区域新增“个股绩效榜单”面板并加载 `symbol_performance` 产物【DoD: 可展示 symbol/收益/回撤/交易数；验证: 打开历史实验可见；风险: 旧实验无该产物时降级展示】
- [x] 3.2 实现排序与筛选交互（默认收益降序，支持按 symbol 过滤）【DoD: 排序与筛选结果稳定；验证: 手工切换排序与筛选回归；风险: 前端状态与当前实验切换不同步】

## 4. 图表叠加与标记

- [x] 4.1 实现主图“组合模式/个股模式”切换并保留基准开关行为【DoD: 两种模式可切换且不互相污染；验证: 切换后图表/文案正确；风险: 图表实例销毁重建导致闪烁】
- [x] 4.2 按选中 symbol 叠加买卖箭头（绿买红卖，时间对齐）【DoD: 仅显示当前 symbol 的 marker；验证: 与 `portfolio_trades.csv` 对账；风险: marker 过多时渲染性能】

## 5. 可观测性与回归验证

- [x] 5.1 增加口径说明与字段注释（前端提示“未平仓为近似估值”）【DoD: 用户可见口径说明；验证: UI 文案与产物字段一致；风险: 文案与实现偏离】
- [x] 5.2 编写端到端回归清单（旧结果兼容、新结果完整）【DoD: 覆盖“有/无 symbol_performance”“有/无交易”场景；验证: 手工回归记录与截图；风险: 仅验证 happy path】
