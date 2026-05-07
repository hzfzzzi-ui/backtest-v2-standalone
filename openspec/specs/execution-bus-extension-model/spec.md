# execution-bus-extension-model Specification

## Purpose
Synced from delta spec during archive. The capability contract is now part of the main spec set.

## Requirements

### Requirement: 新实验逻辑必须只通过两类入口接入
系统 MUST 只允许新实验逻辑通过两类入口接入执行总线：`provider path` 和 `pipeline built-in module path`。其他入口 SHALL NOT 成为正式扩展方式。

#### Scenario: 新增一种信号生成机制
- **WHEN** 需要新增新的信号生成 route 或 `precompute + day_signals` 逻辑
- **THEN** 系统 MUST 使用 `provider path`
- **THEN** 路由映射 MUST 由 `route_registry.py` 管理

#### Scenario: 新增一个过滤或排序模块
- **WHEN** 需要新增 candidate filter、ranker、gate、exit、sizer 或 reporter
- **THEN** 系统 MUST 使用 `pipeline built-in module path`
- **THEN** 模块 MUST 通过 `registry.py` 和 `resolver.py` 接入

### Requirement: provider 必须只负责信号，不得直接记账
系统 MUST 将 provider 限制为 `precompute + day_signals`。provider SHALL NOT 直接修改现金、仓位、NAV 或成交记录。

#### Scenario: provider 生成买卖信号
- **WHEN** provider 计算当日候选、持仓动作或退出信号
- **THEN** provider MUST 只输出信号及其上下文
- **THEN** provider SHALL NOT 直接生成 fill/accounting 结果

#### Scenario: provider 试图写入记账状态
- **WHEN** provider 需要更新现金、仓位或 NAV
- **THEN** 系统 MUST 将其判定为越界设计
- **THEN** 相关逻辑 MUST 移至 planning/fill/accounting 边界

### Requirement: 单轮实验主改动必须保持单层归因
系统 MUST 要求一轮实验的主改动原则上只动 `provider` 或 `pipeline module` 其中一层。两层同时改动 ONLY IF 该变更属于纯接线或迁移型变更。

#### Scenario: 单轮实验修改一个 gate 模块
- **WHEN** 一轮实验只测试新的 gate 规则
- **THEN** 系统 MUST 允许仅修改 pipeline built-in module
- **THEN** 同轮 SHALL NOT 再引入新的 provider 策略改动

#### Scenario: 迁移期接线变更
- **WHEN** 需要把既有逻辑改接到新的 registry 或 resolver
- **THEN** 系统 MAY 同时调整两层接线
- **THEN** 该变更 SHALL NOT 被视为双重策略改动

### Requirement: reporters 只能采集诊断信息
系统 MUST 将 `reporters` 限制为机器读诊断和审计信息采集模块。`reporters` SHALL NOT 影响交易决策。

#### Scenario: reporter 采集 reason code
- **WHEN** reporter 输出 reason code、计数器或调试样本
- **THEN** reporter MUST 只写诊断产物
- **THEN** 交易决策 SHALL 保持不变

#### Scenario: reporter 试图改变候选或订单
- **WHEN** reporter 试图修改候选集、排序结果或订单计划
- **THEN** 系统 MUST 将其判定为越界
- **THEN** 该逻辑 MUST 迁移到 filter/ranker/gate/sizer 等正式模块类型
