## ADDED Requirements

### Requirement: 联合影子实验必须通过正式 study 入口运行

系统 MUST 提供 research-only 的 `stock + ETF` 联合影子 study，并且该 study MUST 通过 `study_run` 执行。该入口 MUST 声明窗口、variant、baseline 对比对象和 required outputs。

#### Scenario: 生成联合影子实验计划

- **WHEN** 用户对联合影子 study 执行 dry-run
- **THEN** 系统 MUST 输出窗口与 variant 的笛卡尔执行计划
- **THEN** 每个计划项 MUST 包含 `window_key`、`variant_name`、`request_payload` 和 `study_meta`

### Requirement: 联合影子实验必须固定 stock sleeve 且只替换 ETF sleeve

系统 MUST 从 `CN_STOCK_ETF_FORMAL_V1` 组合模板复制 stock 组件来源，并在扩池 variant 中仅替换 ETF 组件的 `compile_input.semantic_config`。系统 SHALL NOT 修改股票 alpha、组合权重、信号时点、成交时点或账户层定义。

#### Scenario: 构建扩池组合请求

- **WHEN** runner 构建 `STYLE_SMART_BETA_POOL_V2` 的组合请求
- **THEN** stock component 的 source 与非窗口字段 MUST 保持来自正式组合模板
- **THEN** ETF component 的 semantic config MUST 来自 `etf/cn_etf_research_style_smart_beta_pool_v2`
- **THEN** 组合权重 MUST 保持 stock sleeve 0.5 与 ETF sleeve 0.5

### Requirement: 联合影子实验必须真实应用三窗口边界

系统 MUST 将 study window 的 `start` 与 `end` 同时写入 top-level universe、stock component semantic config 和 ETF component semantic config。系统 SHALL NOT 只修改顶层窗口标签。

#### Scenario: 构建 2012-2017 硬门槛窗口

- **WHEN** runner 构建窗口 `1217`
- **THEN** top-level universe start/end MUST 等于 `2012-01-04` 与 `2017-12-29`
- **THEN** stock component universe start/end MUST 等于 `2012-01-04` 与 `2017-12-29`
- **THEN** ETF component universe start/end MUST 等于 `2012-01-04` 与 `2017-12-29`

### Requirement: 联合影子实验必须防止旧 execution contract 覆盖扩池配置

系统 MUST 在 research-only 请求中移除来自组合模板的旧 `execution_contract` 快照，或以等价方式保证旧 ETF runtime config 不会覆盖当前 variant 的 ETF semantic config。

#### Scenario: 移除旧 execution contract

- **WHEN** runner 构建扩池组合请求
- **THEN** `unified_runtime.execution_contract` MUST 不再携带模板中的旧 ETF runtime config
- **THEN** `unified_runtime.combo_context.component_source_contract` MUST 指向当前 variant 的 ETF component source

### Requirement: 联合影子实验结果必须可归因并标注 research-only

系统 MUST 输出每个运行项的 combo exp_id、stock exp_id、ETF exp_id、窗口、variant、ETF 池版本、关键收益风险指标和相对基线差异。系统 MUST 标注结果为 research-only，并且 SHALL NOT 自动注册或迁移 baseline。

#### Scenario: 写出联合影子实验汇总

- **WHEN** 联合影子 study 完成一次运行
- **THEN** 运行结果 MUST 包含 combo exp_id、stock component exp_id 与 ETF component exp_id
- **THEN** 运行结果 MUST 包含 `research_only=true`
- **THEN** 运行结果 SHALL NOT 写入正式 baseline 注册
