# results-workbench-snapshot-boundary Specification

## Purpose
Synced from delta spec during archive. The capability contract is now part of the main spec set.
## Requirements
### Requirement: 结果工作台必须只消费 snapshot
桌面结果工作台 MUST 只消费 `ResultsWorkbenchSnapshot` 作为唯一输入真相。Vue workbench SHALL NOT 直接调用后端，也 SHALL NOT 直接依赖页面控制器内部字段。

#### Scenario: 页面壳加载实验结果
- **WHEN** 页面壳完成主 surface 与子面的获取
- **THEN** 页面壳 MUST 组装 `ResultsWorkbenchSnapshot`
- **THEN** Vue workbench MUST 仅通过 snapshot 渲染结果

#### Scenario: 页面壳不再直接操纵组件内部状态
- **WHEN** 桌面端切换实验或刷新结果
- **THEN** 页面壳 SHALL 通过更新 snapshot 驱动工作台
- **THEN** 页面壳 SHALL NOT 直接修改图表或表格组件的内部状态

### Requirement: 页面状态必须至少拆成四个切片
桌面研究页面 MUST 将状态至少拆为 `configDraft`、`runSession`、`activeExperiment` 和 `viewState` 四个切片，以避免单一巨型页面控制器继续膨胀。

#### Scenario: 配置编辑与运行状态分离
- **WHEN** 用户修改配置草稿但未提交运行
- **THEN** 系统 MUST 只更新 `configDraft`
- **THEN** `runSession` SHALL 保持独立，不因配置编辑被隐式覆盖

#### Scenario: 视图状态不污染运行配置
- **WHEN** 用户切换图表区间、排序或展开面板
- **THEN** 系统 MUST 只更新 `viewState`
- **THEN** `activeExperiment` 和 `configDraft` SHALL NOT 被视图操作隐式修改

### Requirement: 页面壳必须承担 fetch-build-push 单向职责
桌面页壳 MUST 采用 `fetch -> build snapshot -> push snapshot` 的单向桥接模型。该模型 MUST 成为桌面研究平台与结果工作台之间的唯一正式交互方式。

#### Scenario: 页面壳请求主 surface 和子面
- **WHEN** 用户加载或切换实验
- **THEN** 页面壳 MUST 先获取主 surface
- **THEN** 页面壳 MAY 再按需请求 `nav`、`symbol_stats` 和 `stage_funnel` 子面

#### Scenario: 子面懒加载后更新工作台
- **WHEN** 子面懒加载完成
- **THEN** 页面壳 MUST 重新构建 snapshot 并推送给工作台
- **THEN** 工作台 SHALL 继续只基于 snapshot 更新视图

### Requirement: ResultsWorkbenchSnapshot 必须携带 assetContext
系统 MUST 在 `ResultsWorkbenchSnapshot` 中提供统一的 `assetContext`，至少包含 `asset_scope`、`asset_profile_id`、`asset_family` 和 `market_profile_id`，并作为工作台展示的正式资产真相。

#### Scenario: 页面壳加载实验结果
- **WHEN** 页面壳完成 manifest、surface 和 section 的拉取
- **THEN** 页面壳 MUST 组装包含 `assetContext` 的 snapshot
- **THEN** Vue workbench MUST 通过 snapshot 而不是其他隐式字段理解当前资产归属

#### Scenario: 切换实验时更新资产上下文
- **WHEN** 用户切换到另一个实验
- **THEN** 页面壳 MUST 连同结果 snapshot 一起更新 `assetContext`
- **THEN** 工作台 SHALL NOT 沿用上一个实验的市场语义

### Requirement: 前端不得再从 A 股专属字段推断市场语义
系统 MUST 禁止桌面页壳、旧控制器和 workbench 组件从行业、停牌、benchmark 名称或 A 股专有字段反推资产类型。资产归属 MUST 只来自 `assetContext`。

#### Scenario: 渲染 A 股实验
- **WHEN** 当前实验属于 A 股 profile
- **THEN** 前端 MAY 基于 `assetContext` 显示 A 股专属文案或标签
- **THEN** 前端 SHALL NOT 仅因为存在行业/ST 字段就推断该实验一定是 A 股

### Requirement: 桌面页壳必须按 `assetContext` 驱动品牌与提示文案
系统 MUST 让桌面页壳的品牌标题、资产提示和 A 股专有说明从 `assetContext` 派生，而 SHALL NOT 再把 “A股回测研究台” 作为无条件全局文案。

#### Scenario: 渲染 A 股实验
- **WHEN** snapshot `assetContext.asset_scope='cn_a_equity'`
- **THEN** 页壳 MAY 展示 A 股专有品牌和提示
- **THEN** A 股 universe/成分口径文案 MUST 保持当前行为

#### Scenario: 渲染美股个股实验或配置
- **WHEN** snapshot 或配置 `assetContext.asset_scope='us_equity'`
- **THEN** 页壳 MUST 显示非 A 股品牌或“入口准备中”提示
- **THEN** 页壳 SHALL NOT 继续把 A 股股票池和成分口径文案当成默认真相

### Requirement: 前端 fallback 不得继续把空资产上下文强制写成 `cn_a_equity`
系统 MUST 让前端 fallback 优先读取 config draft、manifest、surface 和 loaded source 中的资产上下文。前端 SHALL NOT 在缺少这些来源时直接把 `cn_a_equity` 写成唯一通用 fallback。

#### Scenario: 加载旧 A 股实验
- **WHEN** 历史实验只在 manifest 或 config 中携带 A 股资产上下文
- **THEN** 前端 MUST 通过这些已有来源恢复 `cn_a_equity`
- **THEN** 前端 SHALL NOT 因为空壳 fallback 逻辑而改变实验资产语义

### Requirement: 桌面研究页必须按 `cn_etf` 资产上下文切换 ETF 研究入口文案
当当前配置草稿、snapshot 或 active experiment 的 `assetContext.asset_scope='cn_etf'` 时，桌面研究页 MUST 切换为 ETF 研究入口文案，并显示 ETF 专属提示。页面 SHALL NOT 继续把“股票池 / 行业 / PIT 成分”作为默认文案真相。

#### Scenario: ETF 配置页切换入口文案
- **WHEN** 用户将资产范围切换为 `cn_etf`
- **THEN** 页面 MUST 把“股票池”切换为 ETF 资产或标的语义
- **THEN** 页面 MUST 隐藏或禁用股票专属过滤控件与股票 PIT 提示

#### Scenario: ETF 结果页渲染 ETF 提示
- **WHEN** 当前实验 `assetContext.asset_scope='cn_etf'`
- **THEN** 结果工作台 MUST 显示 ETF 资产标签与 ETF 研究提示
- **THEN** 工作台 SHALL NOT 使用股票成分股 lineage 文案解释该实验

### Requirement: ResultsWorkbenchSnapshot 必须携带 ETF 研究覆盖与口径摘要
当结果属于 `cn_etf` 时，页面壳 MUST 将 ETF 研究摘要推入 `ResultsWorkbenchSnapshot`，至少包含 ETF 名单、批次、覆盖起止日期、数据表和价格语义，以便工作台和旧壳兼容层能用统一 snapshot 渲染 ETF 结果。

#### Scenario: ETF 运行摘要进入 snapshot
- **WHEN** 页面壳加载 `cn_etf` 实验结果
- **THEN** `ResultsWorkbenchSnapshot` MUST 携带 `etf_symbols`、`etf_batch`、`coverage_start`、`coverage_end`、`daily_table` 和 `price_series_semantics`
- **THEN** 工作台 MUST 基于这些字段展示 ETF 研究摘要

### Requirement: ResultsWorkbenchSnapshot 必须携带Governed A股状态与预算摘要
当结果属于 Governed A 股主线时，`ResultsWorkbenchSnapshot` MUST 携带最小 regime / Governor 摘要，并且这些摘要 MUST 来自正式 regime payload 与 Governor 证据链。

最小摘要至少包括：
- `base_state_5`
- `effective_state_5`
- `coarse_state`
- `effective_coarse_state`
- `regime_confidence`
- `regime_transition_reason`
- `risk_budget_multiplier`
- `defense_bias`
- `total_risk_budget`
- `total_exposure_cap`
- `budget_reason_codes`

前端 SHALL NOT 仅根据 `market_state` 或 `trade_mode` 自行推断上述语义。

#### Scenario: Governed A股 snapshot 暴露正式状态摘要
- **WHEN** 结果工作台加载 Governed A 股实验 snapshot
- **THEN** snapshot MUST 直接提供正式 regime / Governor 摘要，而不是要求前端自行拼装

### Requirement: ResultsWorkbenchSnapshot 必须携带归因审计摘要
当结果属于 Governed A 股主线时，`ResultsWorkbenchSnapshot` MUST 携带最小 attribution 摘要，至少包含：
- `reason_codes`
- `subscores.technical`
- `subscores.sentiment`
- `subscores.macro_global`
- `manual_override.active`
- `manual_override.reason`
- `manual_override.scope`

该摘要 SHALL 用于支持后续 Governor / Regime / Attribution 可视化，而不是只保留在 debug 文件中。

#### Scenario: snapshot 足以支持前端解释状态来源
- **WHEN** 前端渲染 Governed A 股结果概览
- **THEN** snapshot MUST 足以展示状态来源、预算原因和是否存在人工干预
