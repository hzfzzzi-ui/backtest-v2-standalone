# Design: V2 Linear Research Governance

## Context

当前项目已经具备三套不同层级的信息系统：

- `outputs/*` 保存单次运行、候选链路、配置来源和审计产物，是事实证据层
- `openspec/changes/*` 保存设计、任务和能力边界，是变更约束层
- 日常协作目前缺少统一的项目编排层，导致研究主线、阻塞项、UI/API 同步、agent 参与和候选晋级经常混在同一轮对话里推进

从仓库现状看，实验层已经有稳定主键和证据结构，例如 `exp_id`、`config_id`、`config_hash`、`results_dir`、`baseline_exp_id`、`candidate_provenance.json`。这意味着 Linear 不应再承担“记录实验事实”的职责，而应承担“组织研究决策”的职责。

本设计的核心约束有三条：

1. 不改变现有回测、审计、配置治理和候选晋级的事实来源
2. 不把单次实验结果手工迁移到 Linear，避免信息重复和口径失真
3. 允许 agent 参与更新和整理，但保留人类对审计结论和候选晋级的最终裁决权

## Goals / Non-Goals

**Goals:**

- 定义一套适用于本项目的 Linear 工作模型
- 明确研究单元、阻塞单元、合同单元、候选晋级单元的 issue 粒度
- 定义状态机和门禁，确保“先审计，后推进”
- 明确 Linear issue 与 `OpenSpec change`、`outputs/*` 证据目录之间的引用关系
- 明确 agent 可自动执行的动作与必须人工执行的动作
- 给出最小落地顺序，便于先从少量活跃主线试运行

**Non-Goals:**

- 不修改回测引擎、实验 API 或前端工作台逻辑
- 不重构 `outputs/*` 目录结构
- 不要求当前就实现 Linear 双向同步脚本或 webhook
- 不要求当前就完成 Codex MCP 的可用性验证
- 不补录全部历史实验到 Linear

## Decisions

### D1: 三层系统边界固定，不相互替代

- `outputs/*` 是证据源，只负责保存运行事实、配置快照、候选证据、审计摘要
- `OpenSpec` 是设计源，只负责保存变更范围、能力合同、任务分解
- `Linear` 是治理源，只负责保存优先级、责任人、状态、阻塞关系、晋级决策

这样做的原因是仓库已经有较稳定的实验归因主键。如果把 `exp_id`、`perf.json`、`run_meta.json` 再手工搬进 Linear，就会制造第二套真相。

替代方案是“用 Linear issue 直接承载实验摘要和结果表”。拒绝原因是高频实验会快速淹没研究主线，而且手工同步的结果摘要无法替代原始证据。

### D2: Linear issue 只管理四类对象

首批只允许以下四类 issue：

- `Research Spike`：一个研究假设或一个最小可证伪实验单元
- `Audit Blocker`：一个阻塞可信度的风险点，如时间错位、配置漂移、口径污染
- `Candidate Promotion`：一个候选方案是否晋级的决策单元
- `UI/API Contract`：一个跨前后端、跨工作台/报告页/API 的合同变更单元

这样做的原因是这四类对象与当前项目最常见的工作形态一致，而且都能自然链接到 OpenSpec 和实验产物。

替代方案是“按模块建 issue”或“按单次运行建 issue”。前者会让一个研究问题被拆散到多个技术模块，后者会让 Linear 退化成结果流水账。

### D3: Team 与 Project 只按治理边界切，不按实验标签切

建议首批 team 固定为：

- `Research`
- `Platform`
- `Workbench`

建议首批 project 固定为：

- `Reliability Spine`
- `Candidate Track`
- `Workbench Sync`

股票池、策略家族、风险主题只作为 label，不作为 team 或 project。这样可以避免“CSI800 一个项目、HS300_ZZ500 一个项目、BR35 一个项目”的碎片化。

### D4: Research workflow 采用审计前置状态机

Research team 建议采用以下状态：

- `Inbox`
- `Planned`
- `Audit Ready`
- `Running`
- `Reviewing`
- `Passed`
- `Rejected`
- `Blocked`

关键门禁是：

- 未完成审计清单的工作项不得进入 `Running`
- `Candidate Promotion` 只有在证据完整且审计无阻塞时才能进入 `Reviewing`
- `Passed / Rejected` 必须由人工判定，agent 不能自动完成

这样做是为了把 AGENTS.md 中“审计优先于收益优化”的原则固化到流程。

### D5: 证据字段标准化，但只存引用不存副本

每个研究类 issue 必须引用以下字段中的适用项：

- `change_name`
- `baseline_exp_id`
- `variant_exp_id`
- `config_id`
- `config_hash`
- `results_dir`
- `candidate_provenance_path`
- `summary_json_path`
- `summary_md_path`
- `main_change_path`

Linear 中只存这些字段和路径，不复制 `perf.json`、`trades.csv`、`run_meta.json` 内容。结果判定必须回到仓库内原始产物核对。

### D6: Agent 只负责整理和推进，不负责最终裁决

agent 允许执行的动作：

- 创建/更新 `Research Spike`、`Audit Blocker`、`UI/API Contract` 草稿
- 补充证据路径、OpenSpec change 名称、实验摘要链接
- 根据已存在的审计结论推进状态到 `Audit Ready` 或 `Reviewing` 前
- 输出 Project update 草稿

agent 不允许执行的动作：

- 自动将候选标记为 `Passed`
- 自动关闭带有审计疑点的 issue
- 在没有证据路径的情况下生成“通过”结论
- 将 Linear 看板状态视为事实来源反向覆盖实验结论

### D7: MCP 接通不是治理落地前提

本地 `C:\\Users\\hzfzzzi\\.codex\\config.toml` 目前仅能确认存在 `mcp_servers.linear.url`，尚未从配置文件确认 `experimental_use_rmcp_client = true`。因此本设计不把 MCP 可用性作为流程前提。

首轮落地允许纯手工维护 Linear，看板模型先跑通；MCP 只作为后续提效层。这样可以避免把一个“工具接入问题”误当成“治理是否开始”的硬门槛。

## Risks / Trade-offs

- [风险] Linear 看板如果允许按 `exp_id` 建单，很快会再次变成结果流水账
  缓解：issue 模板中显式禁止“一个运行一个 issue”，并要求填写 `single_main_change`

- [风险] 研究与平台协作仍可能因为跨端改动被拆散
  缓解：跨前后端字段合同统一走 `UI/API Contract`，并要求关联 OpenSpec change

- [风险] agent 自动推进状态可能掩盖未审计问题
  缓解：将 `Passed / Rejected`、候选晋级和审计豁免设为人工动作

- [风险] 如果 Codex MCP 未真正可用，用户会误以为治理方案不可执行
  缓解：把手工流程定义为标准路径，把 MCP 自动化定义为增强路径

- [风险] 首批 team / project 过多会加重维护负担
  缓解：限制为 3 个 team、3 个 project、4 个 issue 模板，先跑 1 周再扩展

## Migration Plan

1. 在仓库中固化治理合同，先形成 OpenSpec 变更与后续落地文档
2. 在 Linear 中创建 3 个 team、3 个 project、4 个 issue 模板和一套 Research workflow
3. 只迁入当前活跃主线，不补录所有历史实验
4. 以一个活跃研究 change、一个审计阻塞项、一个 UI/API 合同项作为试运行样本
5. 观察一周：确认状态机是否能真实区分“待审计、运行中、待复核、已淘汰”
6. 若试运行稳定，再决定是否增加自动评论回填、摘要同步或 agent 领单逻辑

回滚策略：

- 如果 Linear 试运行失败，保留 OpenSpec 和 `outputs/*` 现状不变
- 关闭 Linear workflow 不会影响任何实验事实、配置来源或候选证据
- 若后续自动化接入失败，退回人工维护即可，不需要迁移实验数据

## Open Questions

- 首轮是否需要把 `Candidate Promotion` 独立成单独 project，还是先挂在 `Candidate Track`
- 是否要在仓库内补一份 issue 正文模板，方便从本地直接复制到 Linear
- 是否需要增加一个轻量脚本，从 `summary.json` 自动生成 Linear 评论草稿
- MCP 接通后，是否允许 agent 自动创建 issue，还是仅允许更新已存在 issue
