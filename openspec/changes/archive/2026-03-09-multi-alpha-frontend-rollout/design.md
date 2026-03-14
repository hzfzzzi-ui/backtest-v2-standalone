## Context

当前后端已经具备第一阶段多 alpha 组合运行时，真实支持边界是 `breakout_55 + rsi_reversal + REGIME_ROUTE + PREFER_HIGHER_SCORE + SOURCE_ONLY + hard_sleeve_budget`。前端工作台仍保留早期占位控件和旧默认值，既不会生成 `signal_generation.modules`，也仍暴露 `WEIGHTED_SCORE / AND / OR`、`equal_10 / profit_release` 这类当前后端不支持的值，导致页面可编辑但主实验不可稳定运行。

这个 change 只解决“前端真实可用”问题，不重新设计组合引擎，也不扩展新的 alpha。约束是配置必须保持唯一真相，任何对旧配置的处理都不能静默改写；如果历史配置不符合第一阶段支持边界，前端必须显式提示并阻断运行。

## Goals / Non-Goals

**Goals:**
- 让工作台可视化控件直接生成第一阶段多 alpha canonical 配置，并能通过现有公开回测主路径运行。
- 让加载配置、导入实验和保存草稿对多 alpha 配置保持无损回填，不引入字段漂移。
- 让结果区至少能看见组合摘要、组合审计计数和来源归因字段，支持研究审计。
- 保持 baseline 单策略路径默认行为不变。

**Non-Goals:**
- 不新增第二阶段组合模式，不开放 `WEIGHTED_SCORE`、`AND`、`OR`、`unified_rank` 等未落地能力。
- 不新增新的 alpha 模块，不在本 change 中推进动量、更多反转或更多分仓算法。
- 不修改交易时钟、执行核、成本模型和股票池口径。
- 不对后端多 alpha 运行时做大规模重构。

## Decisions

### 决策 1：前端只暴露第一阶段已支持的组合选项
- 决定：工作台中多 alpha 相关控件只允许选择后端当前真实支持的模块和模式，删除或降级旧占位选项，不再把 `WEIGHTED_SCORE / AND / OR` 伪装成可运行能力。
- 原因：当前页面默认值与后端支持矩阵不一致，继续保留会造成“用户可选但运行失败”。
- 备选方案：
  - 保留通用控件并在后端报错。拒绝，因为错误发现太晚，且会污染可用性判断。
  - 前端静默把旧值映射到 `REGIME_ROUTE`。拒绝，因为这会引入口径漂移。

### 决策 2：在 `buildConfigDraft()` 中直接生成 canonical 多 alpha 配置
- 决定：前端草稿层直接输出 `signal_generation.modules`、`signal_composition`、`position_risk.portfolio_mode=hard_sleeve_budget`，而不是继续依赖旧的 `trend/mr/breakout` 占位结构去猜测组合意图。
- 原因：只有直接生成 canonical 配置，前后端才可能做到单一真相和无损 round-trip。
- 备选方案：
  - 保留旧字段，再由后端推断组合配置。拒绝，因为会继续制造字段漂移。
  - 只在 JSON 预览中显示 canonical 结构，页面控件仍使用旧字段。拒绝，因为 UI 与实际运行配置仍会分裂。

### 决策 3：历史不兼容配置采取“显式阻断”而不是“自动迁移”
- 决定：前端在加载配置、导入实验或粘贴 JSON 时，如果发现不支持的组合值，必须显示明确告警并阻断运行，直到用户手工修正。
- 原因：研究系统优先可审计性，不能为了“能跑”而默默替换配置语义。
- 备选方案：
  - 自动把不支持的 `compose_mode`、`portfolio_mode` 映射到最近似值。拒绝，因为会破坏实验可复现性。
  - 允许继续运行，等后端 400。拒绝，因为反馈太晚，且用户不容易理解真实原因。

### 决策 4：结果展示优先复用现有 artifact，不新增后端查询接口
- 决定：结果总览、Markdown 报告和交易明细优先消费现有 `original_workbench_config`、`audit.json`、`orders.csv`、`trades.csv` 字段，不为本次前端上线新增专门 API。
- 原因：后端 contract 已经存在，新增接口只会扩大改动面。
- 备选方案：
  - 新增组合摘要接口。拒绝，因为会引入新的同步点和重复协议。
  - 只更新 report，不更新工作台。拒绝，因为用户仍无法在主界面直观看到组合是否生效。

### 决策 5：同时更新 Vue workbench 主面和 legacy fallback 的最小可读能力
- 决定：主渲染面优先更新 `resultsWorkbenchBridge` 对应的数据消费逻辑，同时为 legacy fallback 保留最小可读摘要，避免不同渲染模式下信息不一致。
- 原因：当前系统在迁移期同时存在 Vue shell 和 legacy fallback，不能只修一条分支。
- 备选方案：
  - 只修 Vue shell。拒绝，因为 fallback 仍会误导用户。
  - 只修 legacy。拒绝，因为主面正在收敛到 Vue shell。

## Risks / Trade-offs

- [风险] 旧配置数量较多，显式阻断会增加短期使用摩擦。 → 缓解：提供清晰的阻断原因、支持从页面直接修正为第一阶段支持值。
- [风险] 前端 summary/report/fallback 三套展示口径不一致。 → 缓解：先统一组合摘要字段名，再分别更新各渲染入口。
- [风险] 组合控件与单策略控件共存时容易误改 baseline。 → 缓解：combo 关闭时不注入任何组合默认值，并保留 baseline 回归校验。
- [风险] 交易来源字段在不同结果面缺失。 → 缓解：所有展示层采用“有值则展示，无值则降级为 `-`”的策略，不因缺列崩溃。

## Migration Plan

1. 先收紧控件与草稿生成口径，让前端只产生后端支持的第一阶段配置。
2. 再补加载配置、导入实验和运行前校验，处理旧配置阻断。
3. 最后补结果摘要、审计计数和交易来源字段展示。
4. 用已有的 `multi_alpha_phase1_acceptance` 样例配置和实验产物做前端验收，不改交易或回测口径。

## Open Questions

- 本 change 默认将来源归因展示做到“摘要 + 报告 + 交易明细最小字段”。如果后续需要按 `alpha_id` 做更完整的交互分析，建议单独开新 change，不并入本次前端上线。
