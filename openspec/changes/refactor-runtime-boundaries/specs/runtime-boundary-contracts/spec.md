## ADDED Requirements

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
