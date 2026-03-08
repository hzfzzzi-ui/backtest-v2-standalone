# V2 Linear Research Governance

## Why

当前仓库已经同时存在 OpenSpec 变更流、实验产物归档、候选晋级链路和前后端并行开发，但缺少一层统一的“研究决策编排”。结果是多轮实验、多股票池、多策略变体、UI 同步建设、agent 参与和可靠性约束被混在一起，任务优先级、责任归属和证据引用都不稳定。

现在引入 Linear 的价值，不是替代 `outputs/*` 的实验事实记录，而是给研究、审计、候选晋级和跨端协同提供统一的治理工作流。若不先定义边界，Linear 很容易退化成手工维护回测结果的看板，进一步放大口径漂移和归因混乱。

## What Changes

- 定义一套面向本项目的 Linear 治理模型，明确 `Linear / OpenSpec / outputs/*` 三层职责边界
- 定义 Linear 中的工作对象粒度，禁止将单次 `exp_id` 运行目录直接当作 issue 管理单元
- 定义研究类 issue 的状态机、审计门禁、候选晋级门禁和人工决策责任
- 定义研究 issue 必填证据字段，包括 `change_name`、`baseline_exp_id`、`config_id`、`config_hash`、`results_dir`、`candidate_provenance` 等引用规范
- 定义 agent 在 Linear 工作流中的权限边界，明确哪些动作允许自动化，哪些动作必须人工确认
- 定义最小落地范围，包括 team / project / label / issue template / project update 的首批配置
- 预留 Codex MCP 接入路径，但不把“已接通 MCP”作为治理方案生效的前置条件

## Capabilities

### New Capabilities
- `linear-research-governance`: 为量化研究项目提供一套与 OpenSpec、实验产物、审计证据兼容的 Linear 治理合同

### Modified Capabilities

无

## Impact

- 流程治理：研究任务拆分、优先级、状态机、审计阻塞和候选晋级方式
- 协作面：Research、Platform、Workbench 三类工作项的责任边界
- 文档面：`docs/ops` 下的治理文档、模板文档、落地清单
- 自动化面：未来可能增加的 Linear issue 评论回填、实验摘要同步、agent 任务领取与状态更新
- 风险控制：避免把实验事实迁移到项目管理系统，保持 `run_meta.json / manifest.json / summary.json / candidate_provenance.json` 继续作为证据源
