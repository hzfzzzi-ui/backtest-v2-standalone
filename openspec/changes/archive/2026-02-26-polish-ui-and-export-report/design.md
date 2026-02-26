## Context

回测工作台前端 (`backtest_v2.js`) 当前使用统一的 `num(v, 4)` 格式化所有数值，导致百分比类指标显示为小数、整数指标带多余小数位。交易明细表仅有基础样式。界面存在大量英文术语。无报告导出功能。

相关文件：
- `frontend/assets/js/backtest_v2.js` — 全部渲染逻辑
- `frontend/index.html` — 页面结构
- `frontend/assets/css/workbench.css` — 样式
- `backend/api/endpoints/backtest_v2_artifacts.py` — artifacts 字典构建

## Goals / Non-Goals

**Goals:**
- 指标按语义类型格式化（百分比 / 比率 / 整数 / 金额）
- 交易明细表专业美化（对齐、标签、配色）
- 全面中文化（KPI 标签、图表图例、计数器名称、reason_code）
- 新增"导出报告"按钮，生成纯 HTML 报告在新标签页打开

**Non-Goals:**
- 报告中不含图表（纯文本 + 表格）
- 不引入新 CDN 库
- 不改变后端 API 接口协议
- 不修改引擎层代码

## Decisions

### D1: 格式化策略 — 语义分类映射表

新增辅助函数 `fmtInt(v)` 显示千分位整数，`fmtMoney(v)` 显示千分位 + 2 位小数。现有 `pct(v)` 和 `num(v, d)` 保留。

KPI 格式化映射：

| 指标 | 中文标签 | 格式函数 | 示例 |
|------|---------|----------|------|
| cagr | 年化收益 | pct | -2.18% |
| max_drawdown | 最大回撤 | pct | -36.91% |
| sharpe | 夏普比率 | num(v,2) | -0.05 |
| calmar | 卡尔马比率 | num(v,2) | 0.00 |
| trades | 交易次数 | fmtInt | 2,166 |
| turnover | 换手率 | pct | 10.95% |
| top10_profit_concentration | Top10集中度 | pct | xx.xx% |
| tier | 评级 | esc (原样) | A |

### D2: 交易明细表改造

- `side` 列：BUY → "买入" 绿色 badge，SELL → "卖出" 红色 badge
- `price` 列：右对齐等宽字体，3 位小数
- `qty` 列：右对齐等宽字体，千分位
- `value` 列：右对齐等宽字体，千分位 + 2 位小数
- `reason_code` 列：翻译为中文（维护 REASON_MAP 字典）
- 行不再用左 border 区分买卖，改为 side 列 badge 配色
- 表头固定（sticky）在滚动区域顶部（已有此 CSS）

### D3: 中文化映射

统一维护一个 `LABEL_MAP` 对象，包含所有英文 → 中文翻译：

```
LABEL_MAP = {
  // KPI
  CAGR: '年化收益', MDD: '最大回撤', Sharpe: '夏普比率', ...
  // 图例
  'Strategy DD': '策略回撤', 'Benchmark DD': '基准回撤',
  // Funnel
  raw_signal: '原始信号', blocked: '被拦截', orders: '下单', ...
  // Explain 计数器
  atr_stop_exit_count: 'ATR止损平仓', ...
  // Execution
  'Candidates TopN': '候选标的 TopN', 'Target positions': '目标持仓',
}
```

Reason code 翻译维护单独的 `REASON_MAP`：
```
REASON_MAP = {
  SMA_CROSS_UP: '均线金叉', SIGNAL_REVERSE: '信号反转',
  ATR_STOP_LOSS: 'ATR止损', ATR_TRAIL_STOP: 'ATR追踪止损',
  TIME_EXIT: '到期平仓', ...
}
```

### D4: 报告生成方案 — 纯前端 HTML 字符串

不引入任何库。在 `backtest_v2.js` 中新增 `generateReport()` 函数：
1. 从 `state.active_artifacts` 读取全部数据（perf、run_meta、navSeries、tradesRows、dailyRows）
2. 组装 HTML 字符串（内联 CSS 样式，自包含）
3. `window.open()` 写入新标签页（`document.write(html)`）
4. 用户可直接 Ctrl+P 打印为 PDF

报告 7 章节结构：

| 章节 | 数据来源 | 内容 |
|------|---------|------|
| §1 概览 | run_meta + perf | 策略名/区间/基准 + KPI 卡片 + 评级 |
| §2 收益分析 | nav.csv + dailyRows | 月度/年度收益表格、累计收益 |
| §3 风险分析 | nav.csv + perf | 最大回撤明细（起止日/幅度/恢复期）、波动率 |
| §4 交易分析 | trades | 买卖次数、reason_code 分布表、盈亏统计 |
| §5 持仓分析 | run_meta.counters + dailyRows | 平均持仓/利用率/约束触发统计 |
| §6 策略参数 | config | 关键参数摘要（非全量 dump） |
| §7 附录 | trades | 全部交易明细表（同页面格式但紧凑版） |

### D5: 后端补充 — artifacts 字典新增 daily

`ensure_standard_artifacts()` 中检测 `portfolio_daily.csv` 是否存在，若存在则添加 `artifacts["daily"]` 键。前端 `loadActiveArtifacts()` 读取并存入 `state.active_artifacts.dailyRows`。

## Risks / Trade-offs

- **报告 HTML 体积**：2166 条交易全量写入附录约 200-300KB HTML，浏览器可处理，但若交易量极大（>10000 条）可能需考虑分页。当前阶段不做分页。
- **reason_code 翻译不全**：可能有未见过的 code，使用 fallback 显示原始值。
- **月度/年度收益计算**：需在前端从 dailyRows 聚合，逻辑相对简单但需确保日期解析正确。
- **portfolio_daily.csv 可能不存在**：老实验可能没有此文件。报告中对应章节显示"数据不可用"即可。
