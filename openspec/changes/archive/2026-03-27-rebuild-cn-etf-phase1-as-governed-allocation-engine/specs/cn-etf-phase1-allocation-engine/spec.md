## ADDED Requirements

### Requirement: ETF Phase 1 正式主线必须作为 Governor 约束下的配置引擎运行
系统 MUST 提供 `cn-etf-phase1-allocation-engine` 能力，将 ETF Phase 1 正式主线定义为 Governor/CTA 约束下的配置引擎，而不是基于 `TopN` 或高自由度筛票链路的轮动器。

#### Scenario: 正式主线进入配置引擎模式
- **WHEN** `cn_etf_beta` 以 `formal_mainline` 方式运行
- **THEN** 系统 MUST 先消费 Governor 下发的 ETF sleeve 预算与执行约束
- **THEN** 系统 MUST 以分配语义生成 ETF 目标，而不是先生成候选筛票结果

### Requirement: ETF Phase 1 必须先完成三桶分配再完成桶内配置
正式 ETF 主线 MUST 先将总预算拆分为 `equity_core_bucket`、`defense_tilt_bucket` 与 `cash_buffer_bucket`，再在桶内生成低自由度目标配置。

#### Scenario: 三桶分配可追溯
- **WHEN** ETF Phase 1 为某个交易日生成配置结果
- **THEN** 系统 MUST 输出三个预算桶的目标值与实际值
- **THEN** 系统 MUST 输出每个预算桶的原因码或等价解释字段

### Requirement: 正式 ETF Phase 1 只能在正式资产池内生成目标
正式 ETF Phase 1 MUST 仅使用 `510300.SH`、`510500.SH`、`510050.SH`、`512100.SH` 作为权益核心资产，且仅允许 `512890.SH` 作为 limited defense candidate。

#### Scenario: 目标配置限定在正式资产池
- **WHEN** ETF Phase 1 生成 `targets`
- **THEN** 权益目标 MUST 只指向四只正式 core beta ETF
- **THEN** 防守倾向目标 MUST 只指向 `512890.SH` 或保留为现金缓冲

### Requirement: ETF Phase 1 必须输出正式配置 contract
正式 ETF Phase 1 MUST 输出 `requested_budget`、`applied_budget`、`targets`、`cash_weight`、`defense_weight`、`reason_codes` 作为正式配置 contract 的最小字段集合。

#### Scenario: 正式配置 contract 完整输出
- **WHEN** 一次 ETF Phase 1 实验完成并产出标准 artifacts
- **THEN** `run_meta` 或等价正式产物 MUST 暴露最小正式配置 contract
- **THEN** 下游 audit 与结果消费层 MUST 可以直接引用这些字段，而不是重新推导 ETF 配置语义
