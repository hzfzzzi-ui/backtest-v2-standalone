## ADDED Requirements

### Requirement: Trend quality soft score AB boundary

系统 SHALL 支持一轮研究专用的股票腿趋势质量软评分 AB。该能力 MUST 只影响股票腿新买入候选的排序或仓位折扣，且 SHALL NOT 改变股票池、PIT 成分、信号日期、成交日期、退出规则、交易成本、账户/NAV 计算或 ETF/组合层逻辑。

#### Scenario: 配置关闭时行为等价

- **WHEN** `trend_quality_soft_score_enabled = false` 或未配置
- **THEN** 股票腿候选、下单、成交、持仓、NAV 和 reason code SHALL 与基线行为保持一致

#### Scenario: 只影响股票腿新买入候选

- **WHEN** `trend_quality_soft_score_enabled = true`
- **THEN** 系统 SHALL 只对股票腿新买入候选应用趋势质量软评分
- **THEN** 系统 SHALL NOT 修改 ETF 腿、组合 allocator、已有持仓退出或成交时点

### Requirement: Trend quality soft score inputs

趋势质量软评分 MUST 只使用入场前可得的价格路径因子，首轮允许因子 SHALL 限定为 `r2_60`、`slope60`、`ret60_vol_adj`、`ret60_dd_adj`。系统 SHALL 使用日内横截面秩或运行期可复现的归一化方式，SHALL NOT 从全周期结果复制固定绝对阈值。

#### Scenario: 使用入场前可得数据

- **WHEN** 系统计算任一交易日的趋势质量软评分
- **THEN** 评分 SHALL 只使用该交易日入场决策前已经可得的 OHLCV 数据
- **THEN** 评分 SHALL NOT 使用未来持仓收益、卖出后表现、TOP30 标签、行业主题后验结论或 shadow 输出作为交易输入

#### Scenario: 禁止固定样本阈值

- **WHEN** 系统配置趋势质量软评分参数
- **THEN** 参数 SHALL 表达为权重、秩分位或可复现归一化规则
- **THEN** 参数 SHALL NOT 使用从全周期样本直接拷贝的绝对收益阈值作为硬门槛

### Requirement: Trend quality soft score AB evidence

趋势质量软评分 AB MUST 输出三窗口对比证据，并至少包含 CAGR、max drawdown、Sharpe、Calmar、total return、交易数、买入数、卖出数、现金不足次数、reason code 差异、候选重排差异和因子分桶表现。

#### Scenario: 主窗口验证

- **WHEN** 运行 `2016-2026` 主窗口 AB
- **THEN** 输出 SHALL 包含基线与候选的 same-window 指标对比
- **THEN** 输出 SHALL 标明 intended diff 是否只来自趋势质量软评分

#### Scenario: 硬门槛验证

- **WHEN** 主窗口结果可解释且继续运行 `2012-2017` 硬门槛窗口
- **THEN** 候选方案 SHALL NOT 以显著恶化 max drawdown 或 Calmar 为代价换取局部收益
- **THEN** 若硬门槛失败，报告 MUST 标记该候选不适合升格

#### Scenario: 全周期审计

- **WHEN** 运行 `2012-2026` 全周期审计
- **THEN** 输出 SHALL 包含全周期结果、分桶结果和相对基线的风险收益差异
- **THEN** 报告 MUST 给出继续、拒绝或保留观察的明确决策
