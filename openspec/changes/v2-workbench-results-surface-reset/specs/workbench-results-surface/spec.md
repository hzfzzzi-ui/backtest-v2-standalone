## ADDED Requirements

### Requirement: 结果页 SHALL 使用结构化结果区替代当前摘要堆叠
前端结果页 MUST 以“8 个 KPI 卡片 + NAV 主图 + 个股筛选 NAV + 中文折叠诊断区”的结构呈现结果。系统 MUST NOT 继续以大段 `Universe摘要 / 策略摘要 / 交易摘要` 作为首要结果说明方式。

#### Scenario: 首屏结果区结构
- **WHEN** 用户加载任意实验结果
- **THEN** 首屏 SHALL 先显示 8 个固定 KPI 卡片
- **THEN** 首屏 SHALL 显示 NAV 主图与个股筛选 NAV
- **THEN** 买入漏斗、卖出漏斗、交易明细、日志 SHALL 以折叠区形式显示在主图之后

### Requirement: 左侧 9 stage 导航 SHALL 可读且可连续操作
左侧 stage 导航 MUST 使用清晰的纵向中文导航组件展示 9 个阶段，并保证用户可以直接识别每个 stage 的含义。系统 MUST NOT 继续使用仅靠单字缩写的窄按钮作为最终形态。

#### Scenario: 导航显示中文阶段名
- **WHEN** 用户打开页面
- **THEN** 左侧导航 SHALL 显示 `股票池 / 大盘环境 / 行业趋势 / 个股趋势 / 个股排序 / 入场信号 / 组合构建 / 风险控制 / 退出`
- **THEN** 每项 SHALL 同时显示阶段编号

### Requirement: 8 个 KPI 卡片 SHALL 与后端产物严格对齐
结果页 MUST 按以下顺序展示 8 个固定 KPI 卡片，且取值必须来自后端产物而非前端重算：
1. 期初资金 / 期末资金
2. 年化收益 / 总收益
3. 最大回撤
4. 夏普比率 / 卡玛比率
5. 交易次数
6. 换手率
7. TOP10 集中度
8. 评级

#### Scenario: KPI 卡片字段一致
- **WHEN** 页面加载某次实验结果
- **THEN** 页面 SHALL 使用 `perf.json` 与 `nav.csv` 渲染 8 个 KPI 卡片
- **THEN** 同名字段的展示值 SHALL 与 `report.html` 保持一致

### Requirement: 诊断区 SHALL 使用中文折叠区并支持平滑展开
结果页诊断区 MUST 使用中文名称的折叠区呈现，并在用户点击时平滑展开到对应区块。系统 MUST 移除 `Explain` 作为结果页主诊断入口。

#### Scenario: 折叠区默认折叠
- **WHEN** 用户首次进入结果页
- **THEN** `买入漏斗 / 卖出漏斗 / 交易明细 / 日志` SHALL 默认折叠

#### Scenario: 点击后平滑展开
- **WHEN** 用户点击任一折叠区标题
- **THEN** 页面 SHALL 平滑展开该区块
- **THEN** 页面 SHALL 平滑滚动到该区块附近，避免排版跳变

### Requirement: 个股筛选 NAV 列表 SHALL 支持滚轮浏览与更高可读性
个股筛选 NAV 区域 MUST 提供固定高度滚动列表、较大的字号和清晰的排序/筛选控件，以支持按标的查看个股级净值与交易表现。

#### Scenario: 列表可滚动
- **WHEN** 个股列表超过容器高度
- **THEN** 用户 SHALL 可以通过鼠标滚轮或触控板在列表中上下滚动

#### Scenario: 个股视图联动
- **WHEN** 用户点击某个标的行
- **THEN** NAV 主图 SHALL 切换到该标的视图
- **THEN** 交易明细 SHALL 能按当前标的进行过滤展示
