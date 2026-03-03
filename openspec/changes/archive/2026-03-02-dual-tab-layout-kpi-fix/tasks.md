## 1. 后端 KPI 字段计算

- [x] 1.1 在 `portfolio_builder.py` 的 `_compute_metrics()` 中添加 calmar 计算：`calmar = cagr / abs(max_drawdown) if max_drawdown != 0 else 0.0`，加入返回的 metrics dict
- [x] 1.2 在 `experiment_runner.py` 的 `run_experiment()` 中从 trade_rows 计算 top10_profit_concentration（按 symbol 聚合利润，Top10 正利润占总正利润比例），加入返回 dict
- [x] 1.3 在 `experiment_runner.py` 中添加 `_compute_tier(sharpe, max_drawdown, calmar)` 函数（T1-T4 分级），在返回 dict 中设置 `tier` 字段
- [x] 1.4 在 `backtest_v2_artifacts.py` 的 `_build_perf()` perf_obj 中添加 `top10_profit_concentration` 和 `tier` 字段

## 2. 前端 KPI 读取修复

- [x] 2.1 在 `artifacts.js` renderPerfPanel() line 385 将 `row.tier` 改为 `p.tier ?? row.tier`

## 3. HTML 结构重组

- [x] 3.1 在 `index.html` 的 `<main class="wb-main">` 开头添加 `wb-main-tabs` Tab Bar（概览 + 分析按钮）
- [x] 3.2 将 `<div class="wb-main-content">` 改为 `<div class="wb-main-panel active" id="wbTabOverview">`，内部内容不变
- [x] 3.3 将 `<section id="wbDock" class="wb-dock">` 替换为 `<div class="wb-main-panel" id="wbTabAnalysis">`，内部包含 `wb-analysis-tabs` 子标签栏 + `wb-analysis-body` 容器，容器内保留 wbDockExplain / wbDockExecution / wbDockLogs 三个面板（保持原 ID）
- [x] 3.4 删除 dock resize handle (`wbDockResize`)

## 4. CSS 样式更新

- [x] 4.1 新增 `.wb-main-tabs`、`.wb-main-tabs button`、`.wb-main-tabs button.active` 样式（参考 dock-tabs 风格）
- [x] 4.2 新增 `.wb-main-panel`（display:none; flex:1; overflow-y:auto）和 `.wb-main-panel.active`（display:flex）样式
- [x] 4.3 新增 `.wb-analysis-tabs` 和 `.wb-analysis-body` 样式
- [x] 4.4 删除 `.wb-dock` 及其子样式（.wb-dock-resize, .wb-dock-head, .wb-dock-tabs, .wb-dock-body），删除 `--wb-dock-h` 变量
- [x] 4.5 将 scrollbar 样式中的 `.wb-dock-panel` 引用更新为新选择器

## 5. JS 事件绑定

- [x] 5.1 在 `backtest_v2.js` 中添加 `switchMainTab(tab)` 函数（切换 wbTabOverview/wbTabAnalysis 的 active 状态 + 按钮高亮）
- [x] 5.2 绑定 `.wb-main-tabs button[data-main-tab]` click 事件到 `switchMainTab()`
- [x] 5.3 删除 dock resize 逻辑（lines 361-375）
- [x] 5.4 在 `ui-controls.js` 的 `switchDockTab()` 中将 `.wb-dock-tabs button` 选择器改为 `.wb-analysis-tabs button[data-dock]`

## 6. 验证

- [x] 6.1 Docker rebuild + 前端回测运行，确认双 Tab 切换正常
- [ ] 6.2 确认 KPI 面板三个字段非空：calmar ≠ 0.00、top10 ≠ —、tier ≠ —
- [ ] 6.3 确认分析 Tab 的 Explain/Execution/Logs 子标签切换正常，内容全高显示
