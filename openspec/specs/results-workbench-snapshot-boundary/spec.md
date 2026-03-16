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

