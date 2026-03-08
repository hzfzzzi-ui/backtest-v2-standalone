# Tasks: v2-linear-research-governance

## 1. 治理合同落地

- [ ] 1.1 在 `docs/ops` 新增 Linear 治理文档，写清三层边界：`Linear = 项目治理`、`OpenSpec = 设计约束`、`outputs/* = 实验证据`
- [ ] 1.2 在治理文档中固化四类 issue 模板：`Research Spike`、`Audit Blocker`、`Candidate Promotion`、`UI/API Contract`
- [ ] 1.3 在治理文档中固化 Research workflow 状态机与人工门禁规则，明确 `Passed / Rejected` 必须人工确认

## 2. Linear 配置清单

- [ ] 2.1 整理首批 team / project / label 清单，限制为 `Research`、`Platform`、`Workbench` 三个 team 和最小项目集
- [ ] 2.2 为每类 issue 定义必填字段模板，至少覆盖 `change_name`、`baseline_exp_id`、`config_id`、`config_hash`、`results_dir`、`candidate_provenance_path`
- [ ] 2.3 定义 issue 与 OpenSpec change、实验产物目录之间的引用写法，并给出一条真实样例

## 3. Agent 协作边界

- [ ] 3.1 定义 agent 允许执行的动作和禁止执行的动作，确保 agent 只能整理与推进，不能替代人工裁决
- [ ] 3.2 如果 Codex MCP 可用，补一份最小操作清单；如果不可用，补一份纯手工流程清单，确保治理方案不依赖 MCP 才能运行

## 4. 试运行与验收

- [ ] 4.1 选择一条活跃研究主线、一条审计阻塞项和一条 UI/API 合同项，按新模板创建试运行样本
- [ ] 4.2 用一周试运行验证：状态机是否能区分待审计、运行中、待复核、已淘汰，且没有把单次 `exp_id` 误建成 issue
- [ ] 4.3 输出试运行复盘，明确保留项、删减项和是否进入自动同步阶段
