## ADDED Requirements

### Requirement: stage 只能消费当日可见的时点数据视图
系统 SHALL 为每个交易日的 stage 执行提供 `DataBundleView`，并限制其只读访问截至当日可见的数据。

#### Scenario: 盘后信号只读到 t 日
- **WHEN** 系统在 `t` 日盘后执行任一 stage
- **THEN** 该 stage SHALL 只能读取截至 `t` 日收盘可见的信号数据

#### Scenario: 次日开盘价不提前暴露
- **WHEN** 系统尚未进入 `t+1` 日开盘成交阶段
- **THEN** 任一 stage SHALL NOT 读取 `t+1` 日开盘价或依赖该价格的派生值

### Requirement: 日循环内禁止数据库与 provider 访问
stage pipeline shell 的主日循环与 stage 模块 SHALL NOT 在循环内部访问数据库、provider 或其他外部数据拉取接口。

#### Scenario: 数据预加载在循环前完成
- **WHEN** stage pipeline shell 开始进入交易日日循环
- **THEN** 所需行情、股票池、基准、行业、ST 和约束数据 SHALL 已由 `DataBundleBuilder` 预加载完成

#### Scenario: stage 不持有 provider 句柄
- **WHEN** 任一 stage 被实例化或执行
- **THEN** 该 stage SHALL 不获得 provider 或数据库连接对象作为输入参数

### Requirement: DataBundle 视图必须保持只读
系统 SHALL 保证 stage 获得的是只读视图，而不是可修改的全量 bundle 对象。

#### Scenario: stage 不得改写 bundle 数据
- **WHEN** 任一 stage 完成执行
- **THEN** stage SHALL NOT 直接修改原始价格矩阵、交易日历、benchmark 序列或 universe 快照

#### Scenario: stage 中间结果与数据边界分离
- **WHEN** 任一 stage 需要缓存本 stage 的筛选结果、分数或约束
- **THEN** 这些结果 SHALL 通过 `StageOutputs` 或 collector 输出，而不是回写到 `DataBundle`
