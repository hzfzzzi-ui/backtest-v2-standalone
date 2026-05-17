## ADDED Requirements

### Requirement: 系统必须持久化研究轮次日志

系统 MUST 提供 research-only 的研究轮次日志，每一轮日志 MUST 至少记录研究问题、主变量、关联 study、baseline、窗口、variant、证据、审计项、判断和下一步动作。研究轮次日志 MUST 保存在 `research/study_journal/rounds/*.json`。

#### Scenario: 创建研究轮次

- **WHEN** 用户创建一个新的 study round
- **THEN** 系统 MUST 生成或接受合法 `round_id`
- **THEN** 系统 MUST 写入 `created_at`、`updated_at` 和 `auto_summary`
- **THEN** 系统 MUST NOT 写入或修改任何 baseline 注册

#### Scenario: 读取研究轮次列表

- **WHEN** 用户打开研究日志页面
- **THEN** 系统 MUST 返回已有研究轮次列表
- **THEN** 列表项 MUST 包含 `round_id`、`title`、`status`、`reliability`、`study_id`、`baseline_id`、`updated_at` 和自动摘要标题

### Requirement: 系统必须提供确定性自动总结

系统 MUST 根据研究轮次字段、关联 evidence 和 study conclusion registry 生成确定性自动总结。系统 SHALL NOT 调用外部模型生成不可复现结论。

#### Scenario: 研究轮次存在关联实验

- **WHEN** 研究轮次关联了一个或多个 `exp_id`
- **THEN** 系统 SHOULD 从 `outputs/studies/conclusions/**/registry.jsonl` 匹配对应 conclusion 记录
- **THEN** 自动总结 MUST 包含 evidence 数量、匹配 conclusion 数量、窗口覆盖、verdict 分布和关键指标摘要

#### Scenario: 证据不足

- **WHEN** 研究轮次没有关联实验或没有匹配 conclusion
- **THEN** 自动总结 MUST 标记可靠性不足
- **THEN** 自动总结 MUST 给出补充证据或补跑窗口的下一步建议

### Requirement: 研究日志 API 必须只管理日志和证据索引

系统 MUST 提供 `/api/research/study-rounds` 系列 API 管理研究轮次，并提供 `/api/research/study-conclusions` 读取 conclusion registry。该 API SHALL NOT 启动回测、修改配置、修改 study runner 或写入 baseline。

#### Scenario: 关联实验证据

- **WHEN** 用户向某个研究轮次关联 `exp_id`
- **THEN** API MUST 将其作为 evidence 写入该轮次
- **THEN** API MUST 刷新自动总结
- **THEN** API MUST NOT 修改 experiment artifact 本身

### Requirement: 研究日志页面必须展示轮次、证据、审计和总结

系统 MUST 提供桌面研究日志页面，用户可以在页面中查看轮次列表、轮次详情、自动总结、证据、审计项、备注和下一步动作。

#### Scenario: 打开研究日志页面

- **WHEN** 用户访问 `/study-journal`
- **THEN** 页面 MUST 加载研究轮次列表
- **THEN** 页面 MUST 支持选择轮次查看详情
- **THEN** 页面 MUST 显示自动总结草案和正式 decision 字段的区别

#### Scenario: 新建并维护研究轮次

- **WHEN** 用户在页面中新建研究轮次、追加备注或关联实验
- **THEN** 页面 MUST 通过正式 API 写入
- **THEN** 页面 MUST 重新加载该轮次并展示刷新后的自动总结

### Requirement: 研究日志必须能嵌入现有回测工作台

系统 MUST 在现有桌面回测工作台提供研究日志入口，并在主内容区嵌入研究日志工作区。嵌入模式 MUST 复用同一套研究日志页面和 API，SHALL NOT 复制研究日志业务逻辑。

#### Scenario: 从回测工作台打开研究日志

- **WHEN** 用户在回测工作台点击“研究”入口
- **THEN** 系统 MUST 显示嵌入式研究日志工作区
- **THEN** 系统 MUST 隐藏结果工作台可见区域，避免两个主内容 owner 同时渲染
- **THEN** 用户 MUST 仍然可以通过 `/study-journal` 独立打开研究日志页面

#### Scenario: 从研究日志切回其他工作区

- **WHEN** 用户从“研究”入口切回配置、历史或其他 rail 面板
- **THEN** 系统 MUST 隐藏嵌入式研究日志
- **THEN** 如果结果工作台已经成功挂载，系统 SHOULD 恢复其可见状态
