## ADDED Requirements

### Requirement: 第一阶段组合策略控件
研究台 SHALL 为第一阶段多 alpha 组合提供可运行的前端控件，并且仅暴露当前运行时已支持的选项：
- 模块：`breakout_55`、`rsi_reversal`
- 组合模式：`REGIME_ROUTE`
- 同股冲突策略：`PREFER_HIGHER_SCORE`
- 持仓所有权：`SOURCE_ONLY`
- 组合仓位模式：`hard_sleeve_budget`

#### Scenario: 组合控件只展示可运行选项
- **WHEN** 用户在工作台启用多 alpha 组合编辑
- **THEN** 页面 SHALL 只展示第一阶段支持的模块与模式
- **THEN** 页面 SHALL 不再把 `WEIGHTED_SCORE`、`AND`、`OR` 或其他未支持选项作为可运行值暴露给主实验

#### Scenario: 单策略路径保持兼容
- **WHEN** 用户未启用多 alpha 组合
- **THEN** 工作台 SHALL 保持现有单策略控件与默认行为
- **THEN** 页面 SHALL 不强制用户填写多 alpha 相关字段

### Requirement: canonical 组合配置草稿生成与回填
工作台 SHALL 从组合控件直接生成并回填 canonical `config_json`，至少包括：
- `signal_generation.modules`
- `signal_composition.compose_mode`
- `signal_composition.same_symbol_policy`
- `signal_composition.holding_ownership`
- `signal_composition.modules`
- `signal_composition.regime_matrix`
- `position_risk.portfolio_mode = hard_sleeve_budget`

#### Scenario: 运行前生成 canonical 多 alpha 配置
- **WHEN** 用户基于工作台草稿运行第一阶段组合策略
- **THEN** 提交给公开回测主路径的 `config_json` SHALL 包含 canonical 多 alpha 配置块
- **THEN** 页面 SHALL 不再只依赖旧的 `signal_generation.trend`、`mr`、`breakout` 占位字段表达组合意图

#### Scenario: 导入实验或配置后无损回填
- **WHEN** 用户加载历史实验配置或已保存配置，且其中包含 canonical 多 alpha 配置
- **THEN** 工作台 SHALL 将这些配置无损回填到对应控件
- **THEN** 再次保存或运行时生成的配置 SHALL 保持与原配置语义一致

#### Scenario: 单策略草稿不被组合默认值污染
- **WHEN** 用户运行或保存未启用多 alpha 组合的草稿
- **THEN** 工作台 SHALL 不注入组合层默认字段
- **THEN** 生成的 `config_json` SHALL 与现有 baseline 单策略口径兼容

### Requirement: 不支持组合配置的显式阻断
工作台 MUST 对不受第一阶段支持的多 alpha 配置给出显式告警，并在用户修正前阻断运行。前端 MUST NOT 静默把不支持的配置值自动改写成可运行值。

#### Scenario: 加载旧组合配置时阻断运行
- **WHEN** 用户加载的配置包含不支持的 `compose_mode`、`same_symbol_policy`、`holding_ownership` 或 `portfolio_mode`
- **THEN** 页面 SHALL 显示明确的“不支持配置”提示
- **THEN** 运行入口 SHALL 被阻断，直到用户将配置改为第一阶段支持值

#### Scenario: 粘贴未知模块配置时阻断运行
- **WHEN** 用户粘贴的 `config_json` 在 `signal_generation.modules` 中包含未知模块
- **THEN** 页面 SHALL 显示未知模块名
- **THEN** 页面 SHALL 不得静默删除该模块后继续运行

### Requirement: 组合结果摘要显示
工作台 SHALL 在结果总览和分析报告中展示组合策略的关键摘要，至少包括：
- 策略类型是否为 `COMPOSITE`
- 已启用模块列表
- `compose_mode`
- `portfolio_mode`
- 关键来源配置摘要

#### Scenario: 组合实验总览展示摘要
- **WHEN** 用户加载一条使用多 alpha 组合运行的实验结果
- **THEN** 总览区 SHALL 展示 `COMPOSITE`、模块列表、`REGIME_ROUTE` 与 `hard_sleeve_budget`
- **THEN** 用户 SHALL 能从结果总览直接判断该实验确实走了组合主链路

#### Scenario: Markdown 报告展示组合摘要
- **WHEN** 用户导出或查看 AI/Markdown 分析报告
- **THEN** 报告 SHALL 包含组合配置摘要，而不只显示旧的单策略字段
- **THEN** 对于未启用组合的实验，报告 SHALL 继续按单策略口径展示

### Requirement: 组合审计与来源归因展示
工作台 SHALL 在结果展示层消费现有组合审计字段与来源归因字段，并在字段缺失时安全降级。可展示字段至少包括：
- `raw_signal_counts_by_alpha`
- `composed_signal_counts_by_alpha`
- `blocked_signal_counts_by_reason`
- `conflict_resolution_counts`
- `source_only_exit_count`
- `global_risk_override_count`
- `entry_alpha_id`
- `entry_sleeve_id`
- `entry_reason_code`
- `exit_owner`

#### Scenario: 组合审计字段被展示
- **WHEN** `audit.json` 或等价产物中包含组合审计摘要
- **THEN** 分析面板或报告 SHALL 展示这些计数
- **THEN** 用户 SHALL 能区分原始信号数量、组合后放行数量、冲突裁决和来源退出统计

#### Scenario: 交易来源字段被展示
- **WHEN** `orders.csv` 或 `trades.csv` 含有来源归因字段
- **THEN** 交易明细或等价详情面板 SHALL 显示这些字段
- **THEN** 用户 SHALL 能追溯每笔交易来自哪个 `alpha_id` 或是否由全局风险覆盖退出

#### Scenario: baseline 缺少组合字段时安全降级
- **WHEN** 用户加载未启用组合的 baseline 实验结果
- **THEN** 页面 SHALL 以 `-` 或空态展示缺失字段
- **THEN** 页面 SHALL 不因缺少组合字段而报错或误判为组合实验
