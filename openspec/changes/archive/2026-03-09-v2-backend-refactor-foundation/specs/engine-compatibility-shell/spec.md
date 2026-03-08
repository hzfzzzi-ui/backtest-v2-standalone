## ADDED Requirements

### Requirement: 新主线必须通过兼容执行壳调用旧计算核
foundation 阶段的公开回测主线 SHALL 通过兼容执行壳调用现有严格引擎计算核，而不是直接重写计算逻辑。

#### Scenario: 兼容壳执行
- **WHEN** 新主线接收到 `compiled_plan.json` 和 `DataBundle`
- **THEN** 兼容执行壳 SHALL 将其转换为旧计算核可消费的输入
- **THEN** 公开运行结果 SHALL 仍由现有严格计算核产出

### Requirement: 公开运行入口必须收敛为单一路径
foundation 阶段 SHALL 只保留一条公开可达的回测执行主线。

#### Scenario: API 触发运行
- **WHEN** 前端或脚本调用公开回测接口
- **THEN** 请求 SHALL 统一进入兼容执行壳
- **THEN** 系统 SHALL NOT 再暴露并行的产品级运行主线

### Requirement: 兼容执行壳在 foundation 阶段不得改变回测语义
兼容执行壳 SHALL 保持与锁定基线一致的成交时点、信号时点、仓位更新和结果写盘语义。

#### Scenario: 保持 T+1 语义
- **WHEN** 兼容执行壳运行一个使用日线收盘信号的策略
- **THEN** 它 SHALL 保持 `t` 日收盘决策、`t+1` 日开盘成交的执行语义

#### Scenario: 保持核心结果一致
- **WHEN** 使用锁定基线对应的语义配置通过兼容执行壳复跑
- **THEN** `portfolio_daily.csv`、`portfolio_trades.csv`、`portfolio_candidates.csv` 和 `perf.json` SHALL 与基线等价

### Requirement: 兼容执行壳必须显式暴露内部边界
兼容执行壳 SHALL 以稳定接口暴露“编译计划输入、数据输入、执行输出”三个边界，便于后续逐层替换旧实现。

#### Scenario: 执行边界可观测
- **WHEN** 一次运行通过兼容执行壳完成
- **THEN** 系统 SHALL 能明确区分 compiler、DataBundleBuilder、legacy engine 和 artifact writer 的责任边界
- **THEN** 任一边界替换后 SHALL 能继续使用锁定基线做等价验证
