## Why

回测工作台的数据展示缺乏专业性：KPI 指标全部显示为 4 位小数原始值（如 CAGR 显示 -0.0218 而非 -2.18%），交易明细表样式简陋，大量英文术语未汉化，且没有导出完整回测报告的功能。作为量化研究台产品，这些问题直接影响用户阅读效率和专业感。

## What Changes

- **数字格式化**：为每个指标建立类型感知的格式化规则——百分比类（CAGR、MDD、换手率等）使用 `pct()` 显示，比率类（Sharpe、Calmar）保留 2 位小数，整数类（Trades）显示千分位，金额类显示千分位 + 2 位小数
- **交易明细美化**：方向列 BUY/SELL 改为"买入/卖出"彩色标签，数字列右对齐等宽字体 + 千分位，reason_code 翻译为中文，整体表格样式提升
- **中文化**：KPI 标签、图表图例、Explain 面板计数器名称、Execution 面板术语全部翻译为中文
- **导出回测报告**：新增纯 HTML 报告生成功能，前端从已有 artifacts 数据组装 7 章节报告（概览、收益分析、风险分析、交易分析、持仓分析、策略参数、附录），无需图表，用户可在浏览器中打开或打印为 PDF

## Capabilities

### New Capabilities
- `backtest-report-export`: 回测报告导出功能——从前端已加载的 artifacts 数据（perf.json、run_meta.json、nav.csv、portfolio_trades.csv、portfolio_daily.csv）生成结构化 HTML 报告

### Modified Capabilities
- `single-run-pipeline`: result 需要额外透传 portfolio_daily.csv 路径到 artifacts 字典，供报告生成使用
- `exit-stats-display`: 面板标签中文化
- `constraint-stats-display`: 面板标签中文化

## Impact

- **前端 JS**：`backtest_v2.js` — 格式化函数增强、renderTradesList 重写、renderPerfPanel/renderExplainPanel 标签替换、新增 renderReport 模块
- **前端 HTML**：`index.html` — 新增"导出报告"按钮
- **前端 CSS**：`workbench.css` — 交易表格样式增强、报告样式
- **后端**：`backtest_v2_artifacts.py` — artifacts 字典新增 `daily` 键指向 portfolio_daily.csv
- **依赖**：无新 CDN 依赖，纯 HTML 字符串生成
