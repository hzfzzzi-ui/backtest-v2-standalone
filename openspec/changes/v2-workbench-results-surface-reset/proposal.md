## Why

当前 workbench 结果页的信息架构已经失去可读性：左侧 stage 导航丑且难用，摘要文字无法帮助判断策略状态，回撤图占空间但价值低，Explain/Execution/Logs 的组织方式也与实际使用习惯脱节。为了让研究结果真正可读、可审计、可操作，结果页需要按“清晰布局 + 阶段漏斗 + 中文折叠诊断”重做。

## What Changes

- 重做左侧 9 个 stage 导航，改为更宽、更清晰、更适合连续操作的纵向导航组件。
- 重排结果状态栏为 8 个固定 KPI 卡片，字段严格与 `perf.json/nav.csv` 对齐。
- **BREAKING**：移除独立回撤曲线区域，用更高密度的 KPI 与漏斗诊断替代。
- 将 `Universe摘要 / 策略摘要 / 交易摘要` 的大段文字改为可读的结构化摘要与默认折叠漏斗区。
- 新增买入漏斗与卖出漏斗：买入漏斗按 stage 展示过滤链路，卖出漏斗按 exit reason 高频到低频排序。
- **BREAKING**：删除 Explain 面板，保留“交易明细”“日志”两个中文折叠区，并支持点击后平滑展开滚动。
- 恢复并优化“个股筛选 NAV”区域的滚动、字号与可读性。

## Capabilities

### New Capabilities
- `workbench-results-surface`: 定义结果页的导航、KPI 卡片、折叠区、图表与诊断信息的最终形态。

### Modified Capabilities
- `daily-funnel-schema`: 买入漏斗需要新增按 stage 可解释的计数器，卖出漏斗需要规范化高频 reason 聚合输出。
- `dual-tab-layout`: 结果页不再以现有 Overview/Analysis/Explain 结构为主，而改为统一结果区 + 折叠诊断区。

## Impact

- 前端：[`frontend/index.html`](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/index.html)、[`frontend/assets/css/workbench.css`](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/css/workbench.css)、[`frontend/assets/js/backtest_v2.js`](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/backtest_v2.js)、[`frontend/assets/js/artifacts.js`](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/artifacts.js)
- 后端产物：`run_meta.json`、`funnel.csv` 或新的 stage funnel 产物、`reason_codes.csv`
- 前后端联动：摘要来源、KPI 展示、漏斗计数、日志与交易明细折叠交互
