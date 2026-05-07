# universe-ui-binding Specification

## Purpose
Frontend UI binding for universe mode selection, including mode toggle buttons, industry picker component, and config draft construction that adapts to the selected universe mode.

## Requirements

### Requirement: 模式按钮交互
4 个 Universe 模式按钮（全A股/沪深300+中证500/自选行业/个股）SHALL 绑定点击事件，点击时更新 hidden select `wbUniverseMode` 的值，切换按钮的 active 样式，并触发 `updateUniverseInputVisibility()`。

#### Scenario: 点击切换模式
- **WHEN** 用户点击"自选行业"按钮
- **THEN** 该按钮 SHALL 变为 active 状态，其余按钮取消 active，`wbUniverseMode` 的值 SHALL 更新为 `INDUSTRY`，行业选择器 SHALL 显示

#### Scenario: 默认模式
- **WHEN** 页面加载完成
- **THEN** "全A股"按钮 SHALL 为 active 状态，`wbUniverseMode` 值为 `ALL_A`

### Requirement: 行业选择器填充
当切换到 INDUSTRY 模式时，行业选择器（`wbIndustryPicker`）SHALL 显示 31 个申万一级行业作为可勾选的 checkbox/chip，支持多选。行业列表 SHALL 从后端 API 获取（不硬编码）。

#### Scenario: 行业列表加载
- **WHEN** 用户首次切换到 INDUSTRY 模式
- **THEN** 系统 SHALL 调用 `GET /api/backtest_v2/industries` 获取行业列表，渲染为可勾选的 chip 组件

#### Scenario: 多行业选择
- **WHEN** 用户勾选"银行"和"非银金融"
- **THEN** `buildConfigDraft()` 构建的配置 SHALL 包含 `industries: ["银行", "非银金融"]`

### Requirement: 行业列表 API
后端 SHALL 提供 `GET /api/backtest_v2/industries` 端点，返回 `pit_industry_history` 表中所有不重复的 `industry_l1` 值列表。

#### Scenario: 返回行业列表
- **WHEN** 客户端调用 `GET /api/backtest_v2/industries`
- **THEN** SHALL 返回 `{"industries": ["农林牧渔", "基础化工", ..., "美容护理"]}` 共 31 个行业

#### Scenario: 表为空时返回空列表
- **WHEN** `pit_industry_history` 表无数据
- **THEN** SHALL 返回 `{"industries": []}`

### Requirement: Config Draft 联动
`buildConfigDraft()` SHALL 根据当前选择的 `universe_mode` 构建不同的配置字段：
- `ALL_A`: 仅传 `universe_mode`
- `HS300_ZZ500`: 仅传 `universe_mode`
- `INDUSTRY`: 传 `universe_mode` + `industries`（已选行业列表）
- `CUSTOM`: 传 `universe_mode` + `symbols`（用户输入的代码列表）

#### Scenario: ALL_A 配置
- **WHEN** 选择 ALL_A 模式，点击运行
- **THEN** 请求体 SHALL 包含 `{"universe_mode": "ALL_A"}` 且 SHALL NOT 包含 `symbols` 字段

#### Scenario: INDUSTRY 配置
- **WHEN** 选择 INDUSTRY 模式，勾选"银行"
- **THEN** 请求体 SHALL 包含 `{"universe_mode": "INDUSTRY", "industries": ["银行"]}`

#### Scenario: CUSTOM 配置兼容
- **WHEN** 选择 CUSTOM 模式，输入 `600519.SH,000001.SZ`
- **THEN** 请求体 SHALL 包含 `{"universe_mode": "CUSTOM", "symbols": ["600519.SH", "000001.SZ"]}`

### Requirement: 股票池基础过滤区 MUST 提供科创板过滤开关
前端 workbench MUST 在股票池基础过滤区域提供科创板过滤 checkbox，并将其视为 `universe.filters.exclude_star_market` 的唯一 UI 输入源。

#### Scenario: 页面默认展示关闭状态
- **WHEN** 用户首次打开 workbench，且配置中未显式提供 `exclude_star_market`
- **THEN** 科创板过滤 checkbox SHALL 处于未勾选状态
- **THEN** 页面 SHALL 不因为默认值而改变既有草稿行为

### Requirement: Config Draft MUST 透传科创板过滤字段
`buildConfigDraft()` MUST 将科创板过滤 checkbox 的状态写入 `universe.filters.exclude_star_market`，保证前端草稿与后端配置协议一致。

#### Scenario: 勾选后构建草稿
- **WHEN** 用户勾选科创板过滤并触发运行
- **THEN** `buildConfigDraft()` SHALL 在请求配置中包含 `universe.filters.exclude_star_market=true`

### Requirement: UI 回填 MUST 恢复科创板过滤状态
`applyConfigToUI()` MUST 从已有配置读取 `universe.filters.exclude_star_market`，并回填到对应 checkbox，保证配置往返一致。

#### Scenario: 已保存配置回填
- **WHEN** 系统载入一个包含 `universe.filters.exclude_star_market=true` 的配置
- **THEN** 科创板过滤 checkbox SHALL 回填为勾选状态
