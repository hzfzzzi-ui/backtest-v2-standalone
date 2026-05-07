# single-run-pipeline Specification

## Purpose
定义单次回测公开主路径的请求模型、编译链路与 baseline 兼容要求，并扩展对多 alpha 组合配置的支持。
## Requirements
### Requirement: API 请求模型包含选股排序字段
`BacktestV2ExperimentRequest` Pydantic 模型 SHALL 包含以下可选字段：
- `enable_strength_rank: bool | None`
- `strength_ma: int | None`
- `strength_top_k_mode: str | None`
- `enable_multifactor_rank: bool | None`
- `mf_topk: int | None`
- `signal_generation: dict | None`
- `signal_composition: dict | None`

其中：
- `signal_generation` SHALL 用于声明 alpha 模块列表及其参数
- `signal_composition` SHALL 用于声明组合模式、同股冲突策略和持仓所有权策略

#### Scenario: API 请求携带选股字段
- **WHEN** HTTP POST 请求 body 包含 `"enable_strength_rank": true`
- **THEN** 请求验证通过，字段值传入 overrides builder

#### Scenario: API 请求携带组合字段
- **WHEN** HTTP POST 请求 body 包含 `signal_generation.modules` 与 `signal_composition.compose_mode`
- **THEN** 请求验证 SHALL 通过
- **THEN** 组合配置 SHALL 传入后端编译链路

#### Scenario: API 请求未携带组合字段
- **WHEN** HTTP POST 请求 body 未包含 `signal_generation` 与 `signal_composition`
- **THEN** 请求验证通过，这两个字段为 `None`
- **THEN** 单次回测 SHALL 继续沿用现有单策略默认行为

### Requirement: 单次回测主路径支持多 alpha 组合编译
单次回测主路径 SHALL 能够将前端提交的组合配置编译为运行时配置，并驱动公开运行路径执行多 alpha 组合回测。

运行时配置 MUST 至少保留以下信息：
- `signal_generation.modules`
- `signal_composition.compose_mode`
- `signal_composition.same_symbol_policy`
- `signal_composition.holding_ownership`

#### Scenario: 编译 breakout 与 RSI 组合
- **WHEN** 单次回测请求同时声明 `breakout_55`、`rsi_reversal`，并设置 `compose_mode = regime_route`
- **THEN** 编译后的运行时配置 SHALL 包含两个独立模块及其 `alpha_id`
- **THEN** 公开运行路径 SHALL 使用该组合配置启动回测

#### Scenario: baseline 请求保持兼容
- **WHEN** 单次回测请求未声明任意组合配置
- **THEN** 运行时配置 SHALL 不注入组合层默认值
- **THEN** 回测结果 SHALL 与现有 baseline 单策略语义兼容

### Requirement: 单次回测公开路径必须由 thin wrapper 调用核心运行服务
单次回测公开路径 MUST 保持 `config_json -> compiler -> DataBundle -> stage pipeline -> artifacts` 主线不变，但 API 层 SHALL 通过核心运行服务进入该主线，而不是由 endpoint 文件直接承载主要编排。

#### Scenario: 同步运行路径
- **WHEN** 用户调用同步实验运行接口
- **THEN** endpoint SHALL 仅负责请求校验、调用 service 与响应包装

#### Scenario: 异步运行路径
- **WHEN** 用户调用异步实验运行接口
- **THEN** job 执行线程最终 SHALL 调用同一核心运行服务
- **THEN** 同步与异步路径不得分叉成两套执行编排

### Requirement: 单次回测必须收口为唯一 execution_contract
单次回测在进入 DataBundle 和 stage pipeline 之前 MUST 收口为唯一 `execution_contract`。该合同 SHALL 是纯参数合同，不得混入 baseline、study 或 replay 引用字段。

#### Scenario: 运行请求带有 baseline 或 study 来源
- **WHEN** 运行请求来自 baseline、study、wrapper 或其它来源对象
- **THEN** 系统 MUST 先把这些来源解析成纯参数 `execution_contract`
- **THEN** 运行时 SHALL NOT 继续根据 `baseline_id`、`study_id`、`linked_exp_id` 或等效引用字段决定执行分支

#### Scenario: 运行产物写出配置快照
- **WHEN** 单次回测执行完成并写出产物
- **THEN** 系统 MUST 明确区分 `execution_contract` 与 `input_config`、`resolved_config`、`compiled_plan`
- **THEN** 后三者 MAY 作为输入快照或 provenance 证据保留
- **THEN** 它们 SHALL NOT 与 `execution_contract` 并列承担执行真相职责

### Requirement: component execution projections MUST materialize before pipeline entry

单腿回测与 unified combo 在进入 DataBundle 与 stage pipeline 前 MUST 先物化纯组件执行合同和唯一 `execution_contract`。

#### Scenario: compiling a unified combo before runtime
- **WHEN** compiler 解析 stock / ETF 组件并准备构造运行载荷
- **THEN** 系统 MUST 先生成纯组件 `runtime_config`
- **THEN** 系统 MUST 再基于这些纯组件合同构造唯一 `execution_contract`
- **THEN** stage pipeline SHALL NOT 接收仍然夹带 provenance 或兄弟腿子树的组件合同

### Requirement: pipeline inputs MUST distinguish execution contracts from compile snapshots

进入 pipeline 的正式输入 MUST 明确区分执行合同与编译快照，禁止直接把 `compiled_plan` 当运行输入。

#### Scenario: bootstrapping a new experiment run
- **WHEN** runtime service 从编译结果启动一次新实验
- **THEN** runtime MUST 从 `execution_contract` 读取正式执行输入
- **THEN** `compiled_plan` SHALL 只作为辅助调试和编译追踪快照

