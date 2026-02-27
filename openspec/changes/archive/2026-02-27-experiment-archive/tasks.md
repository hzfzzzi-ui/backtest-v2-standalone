## 1. 后端基础设施

- [x] 1.1 在 `backtest_v2_artifacts.py` 的 `ensure_standard_artifacts()` 中新增 `stock_names.json` 写入：从 portfolio_trades.csv 提取 symbols，调用 `resolve_stock_names()` 查 DB，写入 JSON 文件。DoD：回测后实验目录出现 stock_names.json，内容为 `{symbol: name}` 映射。
- [x] 1.2 在 `stabilize_experiment_result()` 中将 `tier` 字段写入 `run_meta.json`。DoD：run_meta.json 顶层包含 `"tier"` 字段。
- [x] 1.3 实现 `index.json` 维护逻辑：在 stabilize 完成后追加实验摘要到 `outputs/experiments/index.json`，包含 label 自动生成。DoD：每次回测后 index.json 自动追加一条记录。

## 2. 后端报告生成器

- [x] 2.1 新建 `backend/core/report/report_generator.py`，实现 `generate_report(results_dir: str) -> str` 函数。从实验目录读取 perf.json、run_meta.json、config.json、portfolio_daily.csv、portfolio_trades.csv、funnel.csv、stock_names.json，生成与前端 `generateReport()` 等效的自包含 HTML 报告。DoD：生成的 report.html 在浏览器中打开，包含 §1-§7 全部章节。
- [x] 2.2 在 `stabilize_experiment_result()` 中调用 `generate_report()`，写入 `report.html`；失败时 log 错误但不阻塞。更新 manifest.json 的 artifacts 增加 `"report": "report.html"` 或 null。DoD：回测后实验目录出现 report.html。

## 3. 后端 API 端点

- [x] 3.1 新增 `GET /api/backtest_v2/experiments` — 读 index.json 返回实验列表（倒序），含孤儿记录清理。DoD：curl 返回 JSON 数组。
- [x] 3.2 新增 `GET /api/backtest_v2/experiments/{exp_id}/report` — 返回 report.html（text/html），不存在返回 404。DoD：浏览器直接访问 URL 显示报告。
- [x] 3.3 新增 `DELETE /api/backtest_v2/experiments/{exp_id}` — 删除实验目录 + 更新 index.json。DoD：删除后 GET 列表不再包含该条。
- [x] 3.4 新增 `DELETE /api/backtest_v2/experiments` — 清空 experiments 目录 + 重置 index.json。DoD：清空后 GET 列表返回 `[]`。

## 4. 前端 History 面板

- [x] 4.1 `index.html` — Rail 新增第 5 个图标（历史/时钟），Drawer 新增 `<section data-module="history">` 容器，包含标题栏（「实验历史」+ 清空按钮）和列表容器 `#wbHistoryList`。DoD：点击 Rail 图标切换到 History 面板。
- [x] 4.2 `backtest_v2.js` — 实现 `loadExperimentList()` 调用 GET /experiments，以及 `renderHistoryPanel()` 渲染实验卡片列表（使用 .card + .wb-stat-row 样式）。DoD：面板显示实验卡片，包含标签/指标/按钮/时间。
- [x] 4.3 `backtest_v2.js` — 实现「加载结果」按钮逻辑：获取 exp_id → 设置 state.active_result → loadActiveArtifacts() → renderRightInspector()。DoD：点击后工作台刷新为历史实验的数据。
- [x] 4.4 `backtest_v2.js` — 实现「查看报告」按钮：window.open 到报告 API URL。DoD：新标签打开 report.html。
- [x] 4.5 `backtest_v2.js` — 实现「清空」按钮：confirm 后调用 DELETE /experiments，刷新面板。DoD：清空后面板显示空状态。

## 5. 前端导出报告改造

- [x] 5.1 修改 `generateReport()` — 优先 fetch 后端 report.html，成功则新标签展示；404 时 fallback 到本地生成。DoD：有后端报告时不再前端拼接。

## 6. 数据清理与集成验证

- [x] 6.1 清空容器内所有旧实验目录 `outputs/experiments/exp_*`，确保 index.json 从零开始。
- [x] 6.2 Docker 重建并运行一次回测，验证：(1) 实验目录包含 report.html + stock_names.json (2) index.json 有一条记录 (3) History 面板显示实验卡片 (4) 「查看报告」打开 HTML (5) 「加载结果」刷新工作台 (6) 「导出报告」读取后端 report.html。
