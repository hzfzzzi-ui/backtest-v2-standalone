## ADDED Requirements

### Requirement: V2 回撤修正研究必须保持 stock leg 固定

系统 SHALL 将本轮研究限定为 ETF sleeve 与组合解释层，不得修改 stock alpha 主线。

#### Scenario: 创建本轮研究实验
- **WHEN** 创建 `reduce-cn-stock-etf-v2-drawdown-with-domestic-defense-boundary` 研究实验
- **THEN** stock component MUST 来自既有组合模板或正式 stock anchor
- **THEN** 研究配置 SHALL NOT 修改 stock 选股、排序、退出、成交或风险预算逻辑

### Requirement: 本轮研究必须使用国内 ETF 子池

系统 SHALL 从最近 99 ETF 扩展池中剔除跨境 ETF，并保留剔除证据。

#### Scenario: 生成国内 ETF 研究池
- **WHEN** 系统构建本轮 ETF 候选池
- **THEN** QDII、港股、美股、中概等跨境 ETF MUST 被排除
- **THEN** 产物 MUST 输出被排除 symbol、名称、角色和排除原因

### Requirement: 本轮研究必须分阶段运行

系统 SHALL 按静态分类审计、主窗口实验、硬门槛窗口、全周期审计的顺序推进。

#### Scenario: 运行顺序受控
- **WHEN** 本轮研究启动
- **THEN** 第一阶段 MUST 输出 ETF 分类审计
- **THEN** 第二阶段 MUST 优先运行 `2016-2026`
- **THEN** 只有主窗口结果可解释时，才运行 `2012-2017` 与 `2012-2026`

### Requirement: 本轮研究必须优先审计回撤而非收益

系统 SHALL 将最大回撤、Calmar、弱状态暴露和 sleeve attribution 作为首要结论依据。

#### Scenario: 输出研究结论
- **WHEN** 本轮实验输出结论
- **THEN** 报告 MUST 先比较 `max_drawdown`、`calmar`、弱状态暴露与 attribution
- **THEN** CAGR 只能作为次级指标
- **THEN** 如果收益提高但回撤未改善，结论 MUST 标记为“不建议升级”
