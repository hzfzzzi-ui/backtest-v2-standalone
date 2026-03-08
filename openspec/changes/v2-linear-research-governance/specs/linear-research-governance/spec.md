## ADDED Requirements

### Requirement: Linear 必须只管理研究治理对象
系统 SHALL 将 Linear issue 限制为研究治理对象，而不是实验事实对象。允许的 issue 类型必须至少包括 `Research Spike`、`Audit Blocker`、`Candidate Promotion`、`UI/API Contract` 四类；单次实验运行目录、单个 `exp_id`、单个 `job_id` 不得直接作为独立 issue 粒度。

#### Scenario: 完成一次单次回测运行
- **WHEN** 某次运行只产生新的 `exp_id`、`results_dir` 和产物文件，但没有新的研究假设、审计阻塞、晋级决策或跨端合同变更
- **THEN** 系统必须将该结果记录为已有 issue 的证据更新，而不是新建一个 issue

#### Scenario: 出现新的时间对齐疑点
- **WHEN** 研究过程中发现一个此前未记录的时间错位或数据泄露风险
- **THEN** 系统必须创建或复用一个 `Audit Blocker` issue，而不是把该问题埋入某次实验结果说明中

### Requirement: 研究 issue 必须引用标准证据字段
每个 `Research Spike` 和 `Candidate Promotion` issue MUST 引用适用的标准证据字段，包括 `change_name`、`baseline_exp_id`、`config_id`、`config_hash`、`results_dir`、`candidate_provenance_path`、`summary_json_path`、`main_change_path`。Linear 只允许保存这些字段的引用，不得把 `perf.json`、`run_meta.json`、`trades.csv` 的完整内容复制为事实源。

#### Scenario: 创建研究 issue
- **WHEN** 新建一个 `Research Spike` issue
- **THEN** issue 正文必须包含研究变更名、基线引用和至少一个实验结果路径或待补充占位字段

#### Scenario: 审核候选晋级
- **WHEN** 某个候选方案进入 `Candidate Promotion`
- **THEN** issue 必须引用 `candidate_provenance_path`、`baseline_exp_id` 和候选摘要路径，且结论必须可回溯到仓库产物

### Requirement: Research workflow 必须以审计门禁为前置条件
Research team 的工作流 MUST 提供 `Inbox`、`Planned`、`Audit Ready`、`Running`、`Reviewing`、`Passed`、`Rejected`、`Blocked` 状态，并且任何涉及实验运行或候选晋级的 issue 在未满足审计前置条件时不得进入 `Running` 或 `Reviewing`。

#### Scenario: 审计未完成
- **WHEN** 某个研究 issue 仍存在未解决的未来函数、时间错位或配置漂移疑点
- **THEN** 该 issue 必须停留在 `Blocked` 或 `Audit Ready`，不得进入 `Running`

#### Scenario: 候选方案准备复核
- **WHEN** 候选方案已有完整证据包且审计清单通过
- **THEN** 对应 `Candidate Promotion` issue 才能从 `Running` 或 `Audit Ready` 进入 `Reviewing`

### Requirement: 跨端改动必须通过合同 issue 关联 OpenSpec
任何同时影响前端工作台、后端 API、报告页或产物字段合同的变更 MUST 使用 `UI/API Contract` issue 管理，并且该 issue 必须引用对应的 OpenSpec change 名称。Linear 不得成为这些合同定义的唯一来源。

#### Scenario: 新增工作台字段
- **WHEN** 某个改动同时修改前端配置面板和后端运行参数编译逻辑
- **THEN** 系统必须创建或更新一个 `UI/API Contract` issue，并关联对应 OpenSpec change

#### Scenario: 只有实验结果变化
- **WHEN** 某个实验只改变策略参数或研究结论，而未改变前后端字段合同
- **THEN** 系统不得强制创建 `UI/API Contract` issue

### Requirement: Agent 只能推进流程，不能替代人工裁决
系统 MUST 允许 agent 创建 issue 草稿、补充证据引用、更新说明和推进到非终态状态，但 MUST NOT 允许 agent 自动把 issue 判定为 `Passed`、`Rejected`，也不得在缺少证据引用时生成最终研究结论。

#### Scenario: agent 整理研究证据
- **WHEN** agent 根据现有实验产物补充 `results_dir`、`summary_json_path` 和 `change_name`
- **THEN** agent 可以更新 issue 内容并推进到 `Audit Ready` 或 `Reviewing` 前的状态

#### Scenario: agent 试图直接晋级候选
- **WHEN** agent 在没有人工确认的情况下尝试将 `Candidate Promotion` issue 标记为 `Passed`
- **THEN** 系统必须要求人工复核，不允许自动完成最终晋级
