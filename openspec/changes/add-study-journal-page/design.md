## Context

当前 repo 已有 study definition、study runner 和 study conclusion registry。registry 能记录单次 window/variant 的 verdict 和关键指标，但不能表达一轮研究的上下文，例如主问题、固定假设、跨窗口判断、审计状态、手工备注和下一步动作。

本 change 新增的是研究过程 surface，不是新的实验 runner。自动总结必须是可复现的确定性规则，不接入外部 LLM，不把总结结果写回回测配置，不影响正式 baseline。

## Goals / Non-Goals

**Goals:**

- 提供研究轮次的持久化账本，记录 study 的问题、主变量、固定假设、证据、审计项、结论和下一步。
- 提供确定性自动总结，从结构化字段和 conclusion registry 生成摘要草案。
- 提供桌面页面，能列表查看、新建、编辑、追加笔记、关联实验、刷新总结。
- 支持从现有 `outputs/studies/conclusions/**/registry.jsonl` 读取证据候选。

**Non-Goals:**

- 不调用外部模型自动生成不可复现文本。
- 不修改 study runner、回测执行链、baseline 注册或正式配置语义。
- 不把 `outputs/` 作为研究日志的唯一真相。
- 不自动提升或迁移 baseline。

## Decisions

### Decision 1: 研究日志保存在 `research/study_journal/rounds`

研究轮次是长期知识资产，应当能被 git 跟踪和回滚。因此 canonical 文件放在 `research/study_journal/rounds/<round_id>.json`。

`outputs/` 中的 conclusion registry 只作为证据来源读取。这样能避免把运行产物误当成源码主路径，也能把研究判断和实验产物解耦。

### Decision 2: 自动总结采用确定性规则

V1 自动总结根据以下输入生成：

- 研究轮次的 `primary_question`、`primary_variable`、`fixed_assumptions`、`audit`、`decision`
- 关联 evidence 中的 `exp_id`、`window_key`、`variant_name`
- conclusion registry 中匹配到的 verdict 和关键指标

输出包括：

- `headline`
- `conclusion_draft`
- `reliability`
- `facts`
- `risks`
- `next_actions`
- `metric_highlights`

该总结是草案，不是正式研究决策；用户可以继续编辑 `decision` 和 `key_findings`。

### Decision 3: API 只做研究日志读写和证据索引

新增 API 位于 `/api/research/*`，只负责文件读写、schema 归一化、路径防护、证据索引和自动总结刷新。它不启动回测、不修改配置、不写 baseline。

### Decision 4: 页面独立承载，主工作台只提供入口

新增 `frontend/study-journal.html`、`assets/css/study-journal.css`、`assets/js/study-journal.js`。主工作台可提供入口链接，但研究日志页面不接管结果工作台、不重算实验指标。

### Decision 5: 回测工作台嵌入使用同一研究日志页面

回测页新增 `research` rail 面板，主内容区通过受控 iframe 加载 `/study-journal?embedded=1`。嵌入模式隐藏研究日志自身 topbar，但复用同一份 JS、CSS、API 和持久化文件。

切换到研究日志时，桌面壳隐藏 `#wbResultsWorkbenchMount`，避免结果工作台和研究日志同时成为可见主内容 owner；切回其他面板时，如果 Vue 结果工作台已经 mounted，则恢复结果工作台可见状态。

## Risks / Trade-offs

- [Risk] 用户误把自动总结当作正式结论。缓解：页面和 API 字段明确标注 `auto_summary` 是草案，正式决策仍写入 `decision`。
- [Risk] conclusion registry 与研究轮次证据不完全匹配。缓解：总结中暴露匹配数量和缺失风险。
- [Risk] 文件型持久化并发写入覆盖。缓解：V1 面向单人本地研究，采用最小实现；后续如需要可加版本号或锁。
- [Risk] 页面逻辑污染研究口径。缓解：前端只消费 API，不重算研究核心逻辑，不写回配置。

## Rollback

删除新增 API router、研究日志 service、前端页面、测试和 `research/study_journal/rounds` 示例文件即可回退。正式 baseline、study runner 和历史 experiment artifacts 不受影响。
