## ADDED Requirements

### Requirement: 多实验 KPI 对比表
系统 SHALL 支持用户选择 2-5 个历史实验进行 KPI 并排对比，展示差异列。

#### Scenario: 用户勾选多个实验
- **WHEN** 用户在历史面板中勾选 2-5 个实验卡片
- **THEN** 面板底部 SHALL 出现"对比"按钮，显示已选数量

#### Scenario: 打开 KPI 对比表
- **WHEN** 用户点击"对比"按钮
- **THEN** 系统 SHALL 弹出对比视图，表格列为各实验，行为 KPI 指标
- **THEN** 指标行 SHALL 包含：年化收益(cagr)、最大回撤(max_drawdown)、夏普(sharpe)、卡尔马(calmar)、交易次数(trades)、换手率(turnover)
- **THEN** 每行 SHALL 高亮最优值（收益最高、回撤最小、夏普最高等）

#### Scenario: 对比数据来源
- **WHEN** 对比视图加载
- **THEN** 系统 SHALL 从各实验的 `perf.json` 读取完整 KPI，不仅依赖 index 摘要
- **THEN** 若某实验的 `perf.json` 读取失败，该列 SHALL 显示 "-" 并提示"产物缺失"

#### Scenario: 勾选超过 5 个实验
- **WHEN** 用户尝试勾选第 6 个实验
- **THEN** 系统 SHALL 阻止勾选并提示"最多对比 5 个实验"

### Requirement: NAV 曲线叠加对比
对比视图 SHALL 支持将多个实验的净值曲线叠加在同一图表中。

#### Scenario: 多曲线渲染
- **WHEN** 对比视图打开且已加载各实验的 nav.csv
- **THEN** 图表 SHALL 叠加显示所有实验的 NAV 曲线，每条线使用不同颜色
- **THEN** 图例 SHALL 显示实验 label 和对应颜色

#### Scenario: 日期范围对齐
- **WHEN** 各实验的回测日期范围不完全重叠
- **THEN** 图表 SHALL 以所有实验的并集日期范围为 X 轴
- **THEN** 某实验在特定日期无数据时，该曲线 SHALL 中断（不插值）

#### Scenario: 可选基准线叠加
- **WHEN** 用户勾选"显示基准"选项
- **THEN** 图表 SHALL 额外叠加基准（如沪深300）净值曲线

### Requirement: 对比视图交互
对比视图 SHALL 支持关闭、调整和快捷操作。

#### Scenario: 关闭对比视图
- **WHEN** 用户点击对比视图的关闭按钮或按 Esc
- **THEN** 对比视图 SHALL 关闭，历史面板恢复正常状态，勾选清除

#### Scenario: 从对比加载单个实验
- **WHEN** 用户在对比表中点击某实验列的"加载"按钮
- **THEN** 系统 SHALL 关闭对比视图，加载该实验为当前活跃结果
