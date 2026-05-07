## Why

前端文档已经把结果工作区收敛成 `核心结果 / 图表分析 / 交易与信号 / 阶段漏斗 / 深层审计`，但实现层的主图能力仍远落后于需求：大盘 K 线 + 成交量、最终信号强度、收益图买卖点和交易明细都还没有成为正式默认工作区。只做信息收口而不重做图表层，结果工作区就还不能进入完成态。

## What Changes

- 将结果主图区正式收口为收益曲线与大盘 K 线分析工作区。
- 在收益图中叠加组合/个股/ETF 曲线、最终信号强度、买卖点，并支持点击查看交易明细。
- 在大盘图中提供 K 线 + 成交量的正式默认视图。
- 把低价值诊断内容从图表主工作区移除或降到深层审计。

## Capabilities

### New Capabilities
- `results-chart-analysis-workspace`: 定义结果工作区正式图表分析能力、默认主图结构与交互。

### Modified Capabilities
- `results-workbench-finalization`: 顶层工作区结构改为图表分析优先的信息架构。
- `benchmark-candlestick-display`: 正式默认形态扩展为 K 线 + 成交量。
- `trade-markers-overlay`: 正式支持收益图买卖点与交易明细联动。

## Impact

- 影响模块：`frontend/app/results-workbench`、图表组件、交易明细联动、前端结果信息架构。
- 风险：图表堆叠过多导致首屏性能回退；旧诊断内容迁移不彻底导致重复展示。
