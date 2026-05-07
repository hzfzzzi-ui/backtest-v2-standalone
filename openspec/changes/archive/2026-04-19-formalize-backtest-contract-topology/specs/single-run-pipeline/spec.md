## ADDED Requirements

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
