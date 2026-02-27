## ADDED Requirements

### Requirement: 后端自动生成 report.html
系统 SHALL 在每次回测 stabilize 阶段自动生成 `report.html` 文件，存放在实验目录内。

#### Scenario: 正常生成
- **WHEN** stabilize_experiment_result 完成所有标准产物写入
- **THEN** 系统 SHALL 调用 report_generator.generate_report(results_dir)，生成自包含 HTML 报告写入 results_dir/report.html

#### Scenario: 报告包含完整 7 个章节
- **WHEN** report.html 生成
- **THEN** 报告 SHALL 包含：§1 概览（KPI 卡片）、§2 月度收益表、§3 回撤分析、§4 交易分析（含漏斗和原因分布）、§5 持仓分析、§6 策略参数（5 个子表）、§7 交易明细附录

#### Scenario: 报告自包含
- **WHEN** report.html 生成
- **THEN** 报告 SHALL 使用内联 CSS，无外部依赖，可直接用浏览器打开或 Ctrl+P 打印为 PDF

#### Scenario: 中文股票名显示
- **WHEN** report.html 渲染交易明细且 stock_names.json 存在
- **THEN** 标的列 SHALL 显示中文名称（如「贵州茅台」），原始代码作为 title 属性

#### Scenario: reason_code 中文化
- **WHEN** report.html 渲染交易明细或平仓原因分布
- **THEN** 已知 reason_code SHALL 翻译为中文（SMA_CROSS_UP → 均线金叉），未知 code 显示原始值

#### Scenario: 生成失败不阻塞回测
- **WHEN** report_generator 执行过程中发生异常
- **THEN** 系统 SHALL 记录错误日志，但不影响回测结果的正常返回；manifest.json 中 report 字段为 null
