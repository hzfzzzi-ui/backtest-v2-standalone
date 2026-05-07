## 1. 主图结构定义

- [x] 1.1 定义结果工作区正式主图结构：收益曲线优先，大盘 K 线次之。（DoD: specs 明确默认图表顺序；验证: `openspec validate refactor-results-chart-analysis-workspace` 通过；风险: 旧主图布局仍被保留）
- [x] 1.2 将 `results-workbench-finalization` 收紧到图表分析优先的信息架构。（DoD: delta spec 覆盖顶层结构；验证: 场景完整；风险: 低价值诊断继续抢主入口）

## 2. 图表交互收口

- [x] 2.1 扩展 `benchmark-candlestick-display` 到 K 线 + 成交量默认视图。（DoD: spec 明确最小字段与默认交互；验证: 场景覆盖默认展示；风险: 图表字段契约不足）
- [x] 2.2 扩展 `trade-markers-overlay` 到收益图买卖点与交易明细联动。（DoD: spec 明确点击后行为；验证: 场景覆盖买卖点点击；风险: 交易详情面重复造轮子）

## 3. 迁移与性能

- [x] 3.1 明确图表增强不得破坏渐进加载与首屏响应。（DoD: design/tasks 写明性能约束；验证: 回归要求可读；风险: 图表重构导致结果加载回退）
