## ADDED Requirements

### Requirement: study 运行后的正式结论不得替代 baseline 治理
系统 MUST 将 study 的执行结果解释为研究结论，而不是新的正式 baseline 候选实体。`study_run` 完成后，正式长期留痕应收敛为简短结论记录。

#### Scenario: study_run 完成一次研究矩阵
- **WHEN** `study_run` 完成某个 study 的 window / variant 执行
- **THEN** 系统 MUST 生成该次研究的简短结论记录
- **THEN** 该记录 MUST 指向 baseline、exp_id、window、variant 与 verdict
- **THEN** 系统 SHALL NOT 默认把该结果继续沉淀为并行 baseline 资产

### Requirement: baseline_id 只能表达对照对象，不得表达 baseline 晋升意图
系统 SHALL NOT 通过 `.study.yaml` 中的 `baseline_id` 隐式表达“把结果升格为 baseline”的意图。study 对 baseline 的引用只表示研究对照来源。

#### Scenario: study 指向 active baseline
- **WHEN** study 声明某个 active baseline 作为对照对象
- **THEN** 该 study 只能继承其 compare 语义
- **THEN** study 本身不得因为结果优秀而自动获得 baseline 注册资格
