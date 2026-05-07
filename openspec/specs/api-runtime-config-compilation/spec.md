# api-runtime-config-compilation Specification

## Purpose
定义 runtime config compile 的模块边界，确保 `runner_config_helpers.py` 只保留 facade 与总装配职责，具体配置域编译拆分到独立模块，同时不改变 `baseline_V10.1` 的 runtime config 语义。
## Requirements
### Requirement: Runtime config 编译必须按配置域拆分
系统 MUST 将 workbench/runtime config 编译按配置域拆分为独立模块。`runner_config_helpers.py` SHALL 只保留 facade 和总装配职责，具体编译 MUST 至少拆分为 `base`、`universe`、`signal`、`risk-exit` 和 `bundle` 五类模块。

#### Scenario: 编译 workbench 草稿
- **WHEN** 系统从 workbench 草稿编译 runtime config
- **THEN** facade MUST 调度配置域模块逐块生成 canonical runtime config
- **THEN** 单一 helper 文件 SHALL NOT 再同时承载所有配置域的编译细节

#### Scenario: 编译 locked candidate 请求
- **WHEN** 系统接收 locked candidate 执行请求
- **THEN** 相关 candidate 上下文构建 MUST 与通用 config compile 分层维护
- **THEN** facade MUST 仍提供统一的请求入口

### Requirement: 配置域模块必须返回 canonical partial config
系统 MUST 要求各配置域模块返回可合并的 canonical partial config，而不是直接在任意位置随意修改整棵运行配置。总装配 SHALL 仅发生在 facade 层。

#### Scenario: universe 模块编译
- **WHEN** universe 编译模块处理时间范围、股票池和 filters
- **THEN** 模块 MUST 仅返回 universe 相关 canonical 配置片段
- **THEN** 模块 SHALL NOT 直接写入 signal、risk 或 artifact 相关字段

#### Scenario: signal 模块编译
- **WHEN** signal 编译模块处理 `strategy_pack`、`signal_generation` 和 multi-alpha payload
- **THEN** 模块 MUST 只返回 signal 相关 canonical 配置片段
- **THEN** 其他域的 merge MUST 由 facade 层完成

### Requirement: 编译模块化不得改变 runtime config 语义
系统 MUST 保持拆分前后的 runtime config 语义一致。模块化 SHALL NOT 改变字段名、默认值解释或由 workbench 草稿推导出的运行时口径。

#### Scenario: baseline compile 对照
- **WHEN** 系统对 `baseline_V10.1` 运行一次拆分前后 compile 对照
- **THEN** canonical runtime config 和 semantic bundle MUST 保持等价
- **THEN** 任一差异都 MUST 被视为行为漂移，而不是“结构性优化”

### Requirement: Runtime config compile 必须先编译 asset boundary
系统 MUST 在 runtime config compile 的第一阶段解析 canonical `asset_scope`、`asset_profile` 和 `market_profile`，然后才允许 universe、signal、risk/exit 和 bundle compile 继续执行。

#### Scenario: 编译桌面草稿
- **WHEN** 系统从桌面 config draft 编译 runtime config
- **THEN** compile 流程 MUST 先产出 canonical asset boundary
- **THEN** 后续各配置域模块 MUST 消费这份 boundary，而不是各自重复推断

#### Scenario: 编译 study 运行请求
- **WHEN** 系统从 study 定义编译 runtime config
- **THEN** study 提供的 asset scope MUST 进入 compile 第一阶段
- **THEN** 最终 runtime config 和 semantic bundle MUST 记录该 canonical asset boundary

### Requirement: Config compile 不得再把 A 股默认散落到各配置域
系统 MUST 收口当前散落在 universe、signal、risk/exit 和 builtin config library 中的 A 股隐式默认，使其由 canonical asset boundary 或对应 A 股 adapter 明确提供。

#### Scenario: 编译当前 A 股 baseline
- **WHEN** 系统编译 `baseline_V10.1`
- **THEN** compile 后的 canonical runtime config MUST 与当前 `V10.1` 语义等价
- **THEN** 任何差异 MUST 被视为行为漂移，而不是结构整理

### Requirement: 语义配置校验 MUST 接受科创板过滤字段
后端语义配置 schema MUST 接受 `universe.filters.exclude_star_market` 布尔字段，并将其视为合法的 universe filter 配置项。

#### Scenario: 请求携带布尔开关
- **WHEN** 客户端提交 `universe.filters.exclude_star_market=true`
- **THEN** 语义配置校验 SHALL 通过
- **THEN** 该字段 SHALL 保留在规范化后的配置对象中

### Requirement: Runtime compile MUST 透传科创板过滤字段
运行时配置编译 MUST 将 `universe.filters.exclude_star_market` 原样透传到 canonical runtime config，确保真实回测执行口径与前端草稿一致。

#### Scenario: 编译开启科创板过滤的草稿
- **WHEN** workbench 草稿包含 `universe.filters.exclude_star_market=true`
- **THEN** runtime config SHALL 包含 `universe.filters.exclude_star_market=true`

#### Scenario: 缺省字段保持旧行为
- **WHEN** workbench 草稿未提供 `exclude_star_market`
- **THEN** runtime compile SHALL 不引入改变既有默认口径的隐式真值
- **THEN** 旧配置在编译后 SHALL 继续保持与改动前等价的 runtime 语义

### Requirement: Runtime config compile MUST 编译 canonical market source contract
系统 MUST 以 `canonical_market` 为正式市场数据消费目标编译 runtime config，而不是继续把 `v1`、`v2 runtime` 或 `data_role` 暴露为正式上层数据角色。编译结果 MAY 保留 canonical source reference 作为审计元信息，但 SHALL NOT 再要求上层通过 `data_role` 或具体 `stocks_table` 决定正式市场数据入口。

#### Scenario: 编译 baseline 使用正式默认市场数据入口
- **WHEN** 用户继续使用当前正式默认运行配置
- **THEN** runtime config compile MUST 产出指向 `canonical_market` 的正式市场数据入口
- **THEN** compile 结果 SHALL NOT 继续把 `pams_ohlcv_daily` 作为默认正式股票数据表

#### Scenario: 编译 canonical shadow 对照实验
- **WHEN** 用户或研究配置指定 canonical shadow source 做对照实验
- **THEN** compile 结果 MUST 明确记录 canonical source reference
- **THEN** 运行产物 MUST 能区分该实验是 canonical 对照，而非正式默认入口被隐式切换

### Requirement: Runtime config compile 必须支持显式的 canonical shadow source 切换
系统 MUST 允许 runtime config compile 在不改变正式默认行为的前提下，显式编译出替代性的 canonical market source 引用。该切换 MUST 来自明确的 shadow 配置或 override，而不是由 compile 流程隐式替换默认市场数据入口。

#### Scenario: Shadow 配置编译为 canonical shadow source
- **WHEN** 用户提供 `pams_cn_pg_v2.json` 或等价 shadow override
- **THEN** runtime config compile MUST 产出指向 canonical shadow source 的 source reference 和相应 schema mapping
- **THEN** 其他运行时字段语义 SHALL 与默认配置保持一致

#### Scenario: 默认配置不被隐式切换
- **WHEN** 用户继续使用当前默认运行配置
- **THEN** runtime config compile SHALL 继续产出指向正式默认 `canonical_market` 入口的结果
- **THEN** compile 流程 SHALL NOT 因存在 `v2` 或 compat 表而自动发出 `pams_ohlcv_daily` 或 `pams_ohlcv_daily_v2_runtime` 作为正式默认入口

### Requirement: Runtime compile 必须为 unified combo 物化正式 sleeve anchors
当 runtime config compile 识别到 `cn_stock_etf_v1` unified combo 模板时，编译器 MUST 通过正式 anchor 接口物化两个 sleeve，而不是继续从同一份 workbench template 深拷贝：

- stock sleeve MUST 通过 baseline 记录接口读取正式 `baseline_V10_1`
- ETF sleeve MUST 通过 study 定义接口读取 `etf/cn_etf_first_wave_core` 的主窗口 `1626` 与 `CORE` variant

编译器 SHALL NOT 因为 unified template 中存在 stock/ETF 字段，就绕过上述 anchor 物化流程。

#### Scenario: 编译 cn_stock_etf_v1
- **WHEN** 系统编译 `cn_stock_etf_v1` 的 unified runtime payload
- **THEN** 编译结果中的 stock sleeve MUST 保留正式 `baseline_V10_1` 的主线研究口径
- **THEN** 编译结果中的 ETF sleeve MUST 保留正式 `cn_etf_first_wave_core` 的 stabilizer 研究口径

#### Scenario: 正式 anchor 缺失
- **WHEN** `baseline_V10_1` 或 `etf/cn_etf_first_wave_core` 主窗口 `1626` / `CORE` variant 无法解析
- **THEN** compile MUST 明确失败
- **THEN** 系统 SHALL NOT 静默回退到 unified template 深拷贝语义
