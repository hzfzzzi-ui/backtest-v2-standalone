## ADDED Requirements

### Requirement: 行业排序 SHALL 使用 PIT 行业映射
当策略启用行业强度或行业相对强弱分数时，系统 SHALL 按交易日从 `pit_industry_history` 解析股票所属行业，不得使用“最新有效行业映射”回看历史。

#### Scenario: 历史行业映射按生效区间解析
- **WHEN** 系统在交易日 `t` 为股票计算行业相关分数
- **THEN** 行业映射 SHALL 满足 `start_date <= t` 且 `end_date IS NULL OR end_date > t`
- **THEN** 不得读取 `t` 之后才生效的行业记录

#### Scenario: 缺行业映射时安全回退
- **WHEN** 股票在交易日 `t` 无有效 PIT 行业映射
- **THEN** 系统 SHALL 将行业相关分数字段记为缺失
- **THEN** 不得用最新行业、未来行业或跨期 `bfill` 进行回填

### Requirement: 横截面排序 SHALL 只基于当日候选 universe
残差排序、行业排序、量价质量排序和最终综合评分中的任意横截面 rank / 标准化 SHALL 仅基于交易日 `t` 当日可交易、当日候选样本计算。

#### Scenario: 当日样本边界明确
- **WHEN** 系统在交易日 `t` 计算任一排序分数
- **THEN** 样本集合 SHALL 只包含交易日 `t` 已存在行情、且在 `t` 日可交易的候选股票
- **THEN** 不得混入未来日期、退市后样本或非候选股票

#### Scenario: rolling 窗口只截到 t
- **WHEN** 系统计算 20/60/120 日收益、均线、ATR、成交量均值或局部高低点
- **THEN** rolling 窗口 SHALL 只使用截至交易日 `t` 的历史数据
- **THEN** 不得因为 merge、reindex、fillna 或 groupby 操作引入未来值

### Requirement: multi-alpha 信号仍 SHALL 遵守 t+1 执行
当 breakout 或 pullback 候选使用 `t` 日收盘后数据生成信号和排序分数时，系统 MUST 把订单排到 `t+1` 交易日执行。

#### Scenario: candidate_signals 与 orders 对齐
- **WHEN** `candidate_signals.csv` 中某条候选的 `date = t`
- **THEN** 对应 `orders.csv` 的 `decision_date` SHALL 为 `t`
- **THEN** 对应执行日期 SHALL 为 `t+1` 的下一交易日

#### Scenario: 不允许信号日成交
- **WHEN** 信号来自日频收盘字段
- **THEN** 系统 SHALL 不得在同一交易日 `t` 以该信号直接成交
