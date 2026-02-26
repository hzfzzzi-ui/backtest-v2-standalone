## 1. 格式化函数与映射表

- [x] 1.1 在 `backtest_v2.js` 中 `pct()` 函数附近新增 `fmtInt(v)` 返回千分位整数（如 2166 → "2,166"），`fmtMoney(v)` 返回千分位 + 2 位小数（如 4858 → "4,858.00"）。新增 `REASON_MAP` 字典映射 reason_code → 中文（SMA_CROSS_UP → 均线金叉, SIGNAL_REVERSE → 信号反转, ATR_STOP_LOSS → ATR止损, ATR_TRAIL_STOP → ATR追踪止损, TIME_EXIT → 到期平仓 等），新增 `reasonZh(code)` 辅助函数查 REASON_MAP，未匹配时 fallback 原始值。验证：控制台调用 `fmtInt(2166)` 返回 "2,166"，`reasonZh('SMA_CROSS_UP')` 返回 "均线金叉"。

## 2. KPI 面板格式化 + 中文标签

- [x] 2.1 修改 `renderPerfPanel()` 中 KPI items 数组，将标签替换为中文，并为每项指定格式函数：年化收益 → pct, 最大回撤 → pct, 夏普比率 → num(v,2), 卡尔马比率 → num(v,2), 交易次数 → fmtInt, 换手率 → pct, Top10集中度 → pct, 评级 → esc。验证：KPI 卡片显示 "-2.18%" 而非 "-0.0218"。

## 3. Explain 面板中文化 + 格式修正

- [x] 3.1 修改 `renderExplainPanel()` 中 Funnel 标签：raw_signal → 原始信号, blocked → 被拦截, orders → 下单, skipped → 跳过, closed_trades → 已平仓。修改触发统计表：表头 "counter"/"value" → "计数器"/"值"，行标签翻译为中文（atr_stop_exit_count → ATR止损平仓, atr_trail_exit_count → ATR追踪平仓, atr_trail_update_count → ATR追踪更新, mf_rank_applied_rate → 资金流排名应用率, gate_on_rate → 门控触发率, trend_slope_block_count → 趋势斜率拦截）。计数类使用 `num(v, 0)`，比率类使用 `pct(v)`。验证：Explain 面板全中文显示，计数器为整数、比率为百分比。

## 4. Execution 面板中文化

- [x] 4.1 修改 `renderExecutionPanel()` 中 "Candidates TopN" → "候选标的 TopN"，"Target positions" → "目标持仓"，"Candidates: -" → "候选标的: -"，"Target positions: -" → "目标持仓: -"。验证：Execution 面板文本全中文。

## 5. 图表图例中文化

- [x] 5.1 修改 `renderPerfPanel()` 中回撤图图例 "Strategy DD" → "策略回撤"，"Benchmark DD" → "基准回撤"。验证：回撤图图例显示中文。

## 6. 交易明细表美化

- [x] 6.1 重写 `renderTradesList()` 函数：side 列 BUY → `<span class="wb-badge-buy">买入</span>`，SELL → `<span class="wb-badge-sell">卖出</span>`；price 列 3 位小数右对齐；qty 列 fmtInt 右对齐；value 列 fmtMoney 右对齐；reason_code 列使用 `reasonZh()` 翻译。数字列添加 `class="num"` 以应用右对齐等宽字体。验证：交易表显示中文买卖标签、千分位金额、中文原因。

- [x] 6.2 在 `workbench.css` 中新增 badge 样式：`.wb-badge-buy`（背景 #e8f5e9, 文字 #2e7d32, 圆角 padding）、`.wb-badge-sell`（背景 #ffebee, 文字 #c62828, 圆角 padding）。移除旧的 `.wb-buy`/`.wb-sell` 行边框样式。验证：买入/卖出显示为绿/红色标签。

## 7. 后端 artifacts 补充 daily

- [x] 7.1 在 `backtest_v2_artifacts.py` 的 `ensure_standard_artifacts()` 函数中，检测 `portfolio_daily.csv` 是否存在于 `results_dir`，若存在则添加 `artifacts["daily"] = _to_rel(daily_path, results_dir)`。验证：run 完成后 manifest.json artifacts 中包含 `daily` 键。

## 8. 前端加载 daily 数据

- [x] 8.1 在 `loadActiveArtifacts()` 中新增 daily artifact 读取（同 trades 模式），将 CSV rows 存入 `state.active_artifacts.dailyRows`。验证：回测完成后 `state.active_artifacts.dailyRows` 包含日级数据数组。

## 9. 报告生成功能

- [x] 9.1 在 `backtest_v2.js` 末尾新增 `generateReport()` 函数，从 `state.active_artifacts` 和 `state.active_result` 读取全部数据，组装自包含 HTML 字符串（内联 CSS），通过 `window.open()` + `document.write()` 在新标签页显示。报告包含 7 章节：§1 概览（run_meta + perf KPI 表格）、§2 收益分析（从 dailyRows 计算月度/年度收益表，正值绿色负值红色）、§3 风险分析（最大回撤幅度/起止日期 + 风险指标）、§4 交易分析（买卖次数 + reason_code 分布表 + 信号漏斗）、§5 持仓分析（counters 中持仓/约束统计）、§6 策略参数（config 中关键参数摘要）、§7 附录（全部交易明细表）。验证：点击导出后新标签页显示完整报告，可 Ctrl+P 打印。

- [x] 9.2 在 `index.html` 中 Performance 面板区域添加"导出报告"按钮（`<button id="wbExportReport" class="pill">导出报告</button>`），在 `backtest_v2.js` 中绑定 click 事件调用 `generateReport()`，无结果时提示"请先运行回测"。验证：按钮可见，点击后正确触发报告生成或提示。
