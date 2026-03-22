# runtime-boundary-contracts Specification

## Purpose
Synced from delta spec during archive. The capability contract is now part of the main spec set.
## Requirements
### Requirement: 主系统必须提供薄 manifest 契约
系统 MUST 为每个实验提供薄 `ExperimentManifest` 契约。该契约 MUST 只包含实验身份、配置引用、运行状态、artifact 引用和 compare 引用，SHALL NOT 内嵌完整 `perf`、`surface` 或大体量展示数据。

#### Scenario: 读取实验列表摘要
- **WHEN** 客户端请求实验列表或实验摘要
- **THEN** 系统 MUST 返回 `exp_id`、`baseline_id`、`config_snapshot_ref`、`status`、`created_at` 和最小比较引用
- **THEN** 响应 SHALL NOT 内联完整 `nav`、`symbol_stats` 或 `stage_funnel`

#### Scenario: 读取实验详情入口
- **WHEN** 客户端请求单个实验详情入口
- **THEN** 系统 MUST 返回薄 manifest 及其关联的 artifact 引用
- **THEN** 客户端 SHALL 通过后续 surface 或子接口读取大体量结果面

### Requirement: 主系统必须提供主 surface 和懒加载子面
系统 MUST 提供统一 `ExperimentSurface` 契约作为桌面结果工作台、移动摘要和 baseline 报告的结果真相。主 surface MUST 至少包含 `summary`、`perf`、`audit`、`machine_outputs` 和 `human_outputs`，并 MUST 通过子接口懒加载 `nav`、`drawdown`、`symbol_stats` 和 `stage_funnel`。

#### Scenario: 桌面端加载结果工作台
- **WHEN** 桌面页壳请求实验主 surface
- **THEN** 系统 MUST 返回 `summary`、`perf`、`audit` 和机器读/人读输出引用
- **THEN** 桌面端 SHALL 按需再请求 `nav`、`symbol_stats` 或 `stage_funnel` 子面

#### Scenario: 移动端加载只读摘要
- **WHEN** 移动端请求实验摘要
- **THEN** 系统 MUST 基于 `ExperimentSurface` 派生移动摘要对象
- **THEN** 移动端 SHALL NOT 直接依赖完整 `ExperimentSurface` 作为接口返回

### Requirement: 主系统必须提供统一执行预览契约
系统 MUST 提供统一 `ExecutionPreview` 契约供桌面研究平台、移动只读看板和未来执行侧共享。该契约 MUST 至少包含 `orders`、`target_weights`、`cash_usage`、`risk_flags`、`freshness` 和 `as_of_date`。

#### Scenario: 桌面端查看执行预览
- **WHEN** 桌面端请求执行预览
- **THEN** 系统 MUST 返回统一 `ExecutionPreview` 字段集
- **THEN** 返回结果 SHALL 与移动端摘要和未来执行侧使用的字段含义一致

#### Scenario: 数据陈旧时展示风险
- **WHEN** 执行预览对应的数据已过期或缺少关键依赖
- **THEN** 系统 MUST 在 `risk_flags` 和 `freshness` 中显式标记该状态
- **THEN** 客户端 SHALL 以同一语义展示该风险

### Requirement: 桌面研究页必须以 experiment manifest 和 runtime snapshot 为真相
系统 MUST 让桌面研究页以 `experiment manifest`、`runtime snapshot` 与派生的 `ResultsWorkbenchSnapshot` 为主真相。配置仅作为输入来源之一，页面状态 SHALL NOT 长期以 `config_id` 作为唯一主语义。

系统 MUST 让桌面研究页以 `experiment manifest`、`runtime snapshot` 与派生的 `ResultsWorkbenchSnapshot` 为唯一主真相。配置来源 metadata 仅可作为 provenance 辅助信息，页面状态 SHALL NOT 再以 `config_id` 或 `input_source_meta` 作为主运行语义。

#### Scenario: 桌面页加载历史实验
- **WHEN** 用户从历史列表载入某个实验
- **THEN** 页面状态 MUST 围绕该实验的 manifest、surface 和 runtime snapshot 更新
- **THEN** 页面 SHALL NOT 仅以 `config_id` 解释当前结果真相

#### Scenario: 页面草稿偏离已加载配置
- **WHEN** 用户在页面上修改配置并偏离已加载来源
- **THEN** 页面 MUST 将偏离状态表达为“当前 runtime 草稿与已加载来源不同”
- **THEN** 页面 SHALL NOT 将 `config_id` 视为唯一可运行真相

#### Scenario: 页面草稿偏离已加载来源
- **WHEN** 用户在页面上修改配置并偏离已加载来源
- **THEN** 页面 MUST 将偏离状态表达为“当前 runtime 草稿与已加载来源不同”
- **THEN** 页面 SHALL NOT 将 `config_id` 视为唯一可运行真相### Requirement: Config Draft 必须作为独立核心模块存在
系统 MUST 将“表单输入 -> config draft -> runtime request”的前端配置核心从旧控制器中抽离为独立模块。旧页面控制器 SHALL NOT 继续承担完整配置编译职责。

#### Scenario: 用户修改配置草稿
- **WHEN** 桌面页表单发生修改
- **THEN** 系统 MUST 由独立的 config draft core 更新运行草稿
- **THEN** 旧控制器文件 SHALL 仅负责控件联动和展示提示

### Requirement: manifest 和 runtime snapshot 必须携带薄资产上下文
系统 MUST 在 experiment manifest、runtime snapshot 和派生的结果真相中携带薄资产上下文，至少包括 `asset_scope`、`asset_profile_id`、`asset_family` 和 `market_profile_id`。

#### Scenario: 读取实验 manifest
- **WHEN** 客户端请求某个实验的 manifest
- **THEN** manifest MUST 返回该实验的薄资产上下文
- **THEN** 客户端 SHALL 能在不解析底层 config 的前提下判断实验属于哪类资产边界

#### Scenario: 读取 runtime snapshot
- **WHEN** 桌面页壳构建 runtime snapshot
- **THEN** snapshot MUST 携带与 manifest 一致的资产上下文
- **THEN** 页面 SHALL NOT 继续通过 A 股专属配置字段反推资产语义

### Requirement: surface 必须暴露资产摘要但不内联 market 细节
系统 MUST 在主 surface 中提供可被桌面端、移动端和 baseline 报告复用的薄资产摘要，但 SHALL NOT 把完整 market adapter 细节塞进 surface。

#### Scenario: 桌面端加载主 surface
- **WHEN** 桌面端读取某个实验的主 surface
- **THEN** 响应 MUST 包含薄资产摘要
- **THEN** 响应 SHALL NOT 直接内联完整 market rule 对象


## Synced From close-p0-p1-architecture-gaps

### Requirement: 旧桌面壳与结果工作台之间必须只通过 snapshot bridge 交换结果真相
系统 MUST 将 legacy 桌面壳与 Vue results workbench 之间的结果真相交换收口到 `runtime snapshot / ResultsWorkbenchSnapshot / bridge` 契约。legacy 壳 SHALL NOT 直接承担结果拼装与可见结果渲染职责。

#### Scenario: 加载历史实验
- **WHEN** 用户从历史列表载入一个实验
- **THEN** 桌面壳 MUST 基于 experiment manifest、surface 和 runtime snapshot 构建结果快照
- **THEN** 结果工作台 MUST 通过 bridge 消费该快照
- **THEN** 桌面壳 SHALL NOT 以 `config_id` 或旧 artifact 兜底逻辑重新解释结果真相

#### Scenario: 结果工作台已接管结果区
- **WHEN** results workbench 已经成功挂载
- **THEN** legacy 桌面壳 SHALL NOT 再直接 patch 结果区的可见 KPI、图表、漏斗或交易 DOM
- **THEN** 桌面壳 MAY 继续负责加载态、选中实验状态和桥接元数据

### Requirement: 主系统必须提供持仓感知的 semi-auto reconcile surface
系统 MUST 在 runtime boundary 中提供面向半自动交易链路的 `PositionAwareReconcileSurface`。该 surface SHALL 至少包含：
- `strategy_source`
- `account_id`
- `holding_sync`
- `snapshot_id`
- `reconcile_id`
- `as_of_date`
- `positions`
- `action_sheet`
- `freshness`
- `risk_flags`

该 surface MUST 与现有 experiment surface / execution preview 分层，而 SHALL NOT 由客户端自行把多个底层产物临时拼接成真相。

#### Scenario: 手机端读取最新动作单真相
- **WHEN** 手机端请求半自动交易所需的聚合结果
- **THEN** 后端 MUST 返回 `PositionAwareReconcileSurface`
- **THEN** 客户端 SHALL 能直接读取当前持仓、动作单和 freshness，而不必自己拼接实验成交和 preview 差集

#### Scenario: reconcile surface 不可用时显式返回降级状态
- **WHEN** 最新持仓快照缺失、最新 reconcile run 失败，或当前仍处于 experiment fallback 模式
- **THEN** surface MUST 显式返回 `status` / `source_mode` / `warnings`
- **THEN** 客户端 SHALL NOT 把缺失 surface 误判为“当前无动作”

### Requirement: reconcile surface 必须携带并发校验令牌
系统 MUST 在 reconcile surface 和移动端动作卡中返回足以做并发校验的令牌，至少包括 `snapshot_id`、`reconcile_id` 和 `as_of_date`。任何确认请求若引用的令牌已落后于系统最新有效 surface，服务端 MUST 拒绝该请求。

#### Scenario: 用户确认基于旧 snapshot 的动作卡
- **WHEN** 用户准备确认某张动作卡，但系统最新有效 `snapshot_id` 或 `reconcile_id` 已变化
- **THEN** 服务端 MUST 返回冲突状态
- **THEN** 客户端 SHALL 提示用户先刷新动作单再确认

#### Scenario: 当前版本仍处于 experiment fallback
- **WHEN** 聚合接口返回 `source_mode=experiment_fallback`
- **THEN** 服务端 SHALL NOT 生成可用于真实持仓确认的并发令牌
- **THEN** 客户端 SHALL 显式提示该模式仅供只读参考

### Requirement: Config Draft 必须作为独立核心模块存在
系统 MUST 将“表单输入 -> config draft -> runtime request”的前端配置核心从旧控制器中抽离为独立模块。旧页面控制器 SHALL NOT 继续承担完整配置编译职责。

#### Scenario: 用户修改配置草稿
- **WHEN** 桌面页表单发生修改
- **THEN** 系统 MUST 由独立的 config draft core 更新运行草稿
- **THEN** 旧控制器文件 SHALL 仅负责控件联动和展示提示

#### Scenario: 新资产接入复用配置核心
- **WHEN** 系统接入新的资产类型或新的 runtime source
- **THEN** 配置核心 MUST 允许复用统一的 draft 和 request 编译流程
- **THEN** 旧控制器 SHALL NOT 再通过资产特化分支继续膨胀

