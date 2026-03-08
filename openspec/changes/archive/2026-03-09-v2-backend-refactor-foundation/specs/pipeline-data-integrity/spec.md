## ADDED Requirements

### Requirement: 引擎运行前必须构建只读 DataBundle
系统 SHALL 在回测主循环开始前构建只读 `DataBundle`，并以该 bundle 作为引擎运行的唯一数据输入。

#### Scenario: 预加载数据
- **WHEN** 一次回测进入执行阶段
- **THEN** 系统 SHALL 先完成 universe、行情、benchmark、交易日历、ST、行业映射及相关约束数据的预加载
- **THEN** 这些数据 SHALL 被封装为只读 `DataBundle`

### Requirement: 日循环内禁止再次查库
系统 SHALL 禁止在回测日循环内部直接访问数据库或重新请求 provider。

#### Scenario: 单日循环执行
- **WHEN** 引擎开始遍历交易日
- **THEN** 所有价格、可交易性、行业和风控所需数据 SHALL 来自 `DataBundle`
- **THEN** 主循环 SHALL NOT 发起新的数据库查询

### Requirement: DataBundle 必须包含时间对齐与完备性摘要
系统 SHALL 在构建 `DataBundle` 时输出时间对齐和完备性检查摘要，用于审计与回归判断。

#### Scenario: 数据质量检查
- **WHEN** `DataBundle` 构建完成
- **THEN** 系统 SHALL 记录 trading_days_count、symbols_count、缺失率、基准对齐状态和关键约束数据覆盖情况
- **THEN** 这些摘要 SHALL 可被写入 `run_meta.json` 或等价产物

### Requirement: 动态入池语义必须来自 bundle 内部时点数据
系统 SHALL 要求动态 universe 或逐日 tradable 判定只基于 `DataBundle` 中该日可见的数据计算。

#### Scenario: 动态入池过滤
- **WHEN** 策略使用 ALL_A 或其他逐日 universe 过滤模式
- **THEN** 当日 tradable 集合 SHALL 只依赖 `DataBundle` 中截至该日可见的数据
- **THEN** 系统 SHALL NOT 通过日循环中的临时查库补充未来时点信息
