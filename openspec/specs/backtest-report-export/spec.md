# backtest-report-export Specification

## Purpose
TBD - created by syncing change polish-ui-and-export-report. Update Purpose after archive.

## Requirements

### Requirement: 导出回测报告按钮
工作台 SHALL 提供"导出报告"按钮，点击后在新浏览器标签页中打开一份自包含的 HTML 回测分析报告。

#### Scenario: 回测完成后导出
- **WHEN** 用户点击"导出报告"按钮且当前有已完成的回测结果
- **THEN** 系统 SHALL 在新标签页中生成并显示完整 HTML 报告
- **THEN** 报告 SHALL 使用内联 CSS，无外部依赖，可直接 Ctrl+P 打印为 PDF

#### Scenario: 无回测结果时导出
- **WHEN** 用户点击"导出报告"按钮但无已完成的回测结果
- **THEN** 系统 SHALL 提示"请先运行回测"

### Requirement: 报告包含概览章节
报告 §1 概览 SHALL 包含策略基本信息和核心 KPI。

#### Scenario: 概览内容
- **WHEN** 报告生成
- **THEN** §1 SHALL 显示：实验 ID、回测区间（起止日期）、基准指数代码
- **THEN** §1 SHALL 显示 KPI 卡片：年化收益（%）、最大回撤（%）、夏普比率、卡尔马比率、交易次数、换手率
- **THEN** §1 SHALL 显示策略评级（Tier）

### Requirement: 报告包含收益分析章节
报告 §2 收益分析 SHALL 包含月度和年度收益统计表格。

#### Scenario: 月度收益表
- **WHEN** 报告生成且 NAV 数据可用
- **THEN** §2 SHALL 包含月度收益表格，行为年份，列为 1-12 月 + 年度合计
- **THEN** 每格显示该月收益率（%），正值绿色、负值红色

#### Scenario: NAV 数据不可用
- **WHEN** 报告生成但 NAV 数据缺失
- **THEN** §2 SHALL 显示"NAV 数据不可用"

### Requirement: 报告包含风险分析章节
报告 §3 风险分析 SHALL 包含最大回撤明细。

#### Scenario: 回撤明细
- **WHEN** 报告生成且 NAV 数据可用
- **THEN** §3 SHALL 显示最大回撤幅度、回撤起始日期、回撤最低点日期
- **THEN** §3 SHALL 显示风险指标：夏普比率、卡尔马比率

### Requirement: 报告包含交易分析章节
报告 §4 交易分析 SHALL 包含交易统计和平仓原因分布。

#### Scenario: 交易统计
- **WHEN** 报告生成且交易数据可用
- **THEN** §4 SHALL 显示：总交易次数、买入次数、卖出次数
- **THEN** §4 SHALL 显示平仓原因分布表（reason_code 及对应次数，中文翻译）

#### Scenario: 信号漏斗
- **WHEN** 报告生成且漏斗数据可用
- **THEN** §4 SHALL 显示信号漏斗：原始信号 → 被拦截 → 下单 → 跳过 → 已平仓

### Requirement: 报告包含持仓分析章节
报告 §5 持仓分析 SHALL 包含持仓利用率和约束触发统计。

#### Scenario: 持仓统计
- **WHEN** 报告生成且 counters 数据可用
- **THEN** §5 SHALL 显示：平均持仓数、最大持仓数、空余仓位、仓位利用率（%）
- **THEN** §5 SHALL 显示约束触发统计：个股上限触发、行业上限触发、资金不足跳过、最小手数跳过

### Requirement: 报告包含策略参数章节
报告 §6 策略参数 SHALL 包含关键配置参数摘要。

#### Scenario: 参数摘要
- **WHEN** 报告生成且 config 数据可用
- **THEN** §6 SHALL 显示关键参数：引擎模式、最大持仓数、信号参数、风控参数
- **THEN** §6 SHALL NOT 显示完整 config dump（仅摘要）

### Requirement: 报告包含交易明细附录
报告 §7 附录 SHALL 包含全部交易记录明细表。

#### Scenario: 交易明细表
- **WHEN** 报告生成且交易数据可用
- **THEN** §7 SHALL 包含全部交易记录表格，列为：日期、标的、方向、价格、数量、金额、原因
- **THEN** 方向列 SHALL 显示中文（买入/卖出）
- **THEN** 金额列 SHALL 显示千分位格式

### Requirement: 数据格式专业化显示
工作台所有数值 SHALL 按语义类型使用对应格式函数显示。

#### Scenario: KPI 卡片格式化
- **WHEN** KPI 面板渲染
- **THEN** 年化收益、最大回撤、换手率、Top10集中度 SHALL 显示为百分比（如 -2.18%）
- **THEN** 夏普比率、卡尔马比率 SHALL 显示 2 位小数（如 -0.05）
- **THEN** 交易次数 SHALL 显示千分位整数（如 2,166）

#### Scenario: 交易明细表格式化
- **WHEN** 交易明细表渲染
- **THEN** 价格 SHALL 显示 3 位小数
- **THEN** 数量 SHALL 显示千分位整数
- **THEN** 金额 SHALL 显示千分位 + 2 位小数

#### Scenario: Explain 面板计数器格式化
- **WHEN** Explain 面板触发统计渲染
- **THEN** 计数类指标（exit count、block count）SHALL 显示为整数
- **THEN** 比率类指标（applied_rate、on_rate）SHALL 显示为百分比

### Requirement: 界面中文化
工作台 SHALL 将所有英文标签翻译为中文（保留技术缩写如 ATR、SMA）。

#### Scenario: KPI 标签中文化
- **WHEN** KPI 面板渲染
- **THEN** 标签 SHALL 为：年化收益、最大回撤、夏普比率、卡尔马比率、交易次数、换手率、Top10集中度、评级

#### Scenario: 图表图例中文化
- **WHEN** 回撤图渲染
- **THEN** 图例 SHALL 显示"策略回撤"和"基准回撤"

#### Scenario: Explain 面板中文化
- **WHEN** 触发统计表渲染
- **THEN** 表头 SHALL 为"计数器"和"值"
- **THEN** 计数器名称 SHALL 翻译为中文（如 atr_stop_exit_count → ATR止损平仓）

#### Scenario: Execution 面板中文化
- **WHEN** Execution 面板渲染
- **THEN** "Candidates TopN" SHALL 显示为"候选标的 TopN"
- **THEN** "Target positions" SHALL 显示为"目标持仓"

#### Scenario: 交易原因码中文化
- **WHEN** 交易明细或报告中显示 reason_code
- **THEN** 已知 reason_code SHALL 翻译为中文（SMA_CROSS_UP → 均线金叉）
- **THEN** 未知 reason_code SHALL 显示原始值作为 fallback

### Requirement: 交易明细表美化
交易明细表 SHALL 具备专业金融软件的视觉品质。

#### Scenario: 方向列样式
- **WHEN** 交易明细表渲染
- **THEN** 买入 SHALL 显示为绿色 badge 标签
- **THEN** 卖出 SHALL 显示为红色 badge 标签

#### Scenario: 数字列对齐
- **WHEN** 交易明细表渲染
- **THEN** 价格、数量、金额列 SHALL 右对齐并使用等宽字体
