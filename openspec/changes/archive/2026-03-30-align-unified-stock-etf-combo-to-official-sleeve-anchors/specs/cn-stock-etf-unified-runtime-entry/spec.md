## ADDED Requirements

### Requirement: Unified combo 研究入口必须消费正式 sleeve anchors
当系统以 `cn_stock_etf_v1` 进入 unified stock+ETF combo 研究入口时，系统 MUST 将 stock sleeve 物化为正式 `baseline_V10_1`，并将 ETF sleeve 物化为正式 `etf/cn_etf_first_wave_core` study 的主窗口与 `CORE` variant。系统 SHALL NOT 再从 unified workbench template 深拷贝两个 sleeve 并假装它们代表正式组件。

#### Scenario: 编译 unified combo research payload
- **WHEN** 系统编译 `cn_stock_etf_v1` 的 unified runtime payload
- **THEN** stock sleeve 的 semantic config MUST 来自 `baseline_V10_1`
- **THEN** ETF sleeve 的 semantic config MUST 来自 `etf/cn_etf_first_wave_core` 主窗口 `1626` 与 `CORE` variant

### Requirement: Unified combo 研究入口必须显式声明 research-only 组件来源
当 unified combo 运行时，系统 MUST 在 `compiled_plan` 与 `run_meta` 中写出组件来源元数据，至少包括 `component_source_mode`、stock baseline id、ETF study id、window key、variant name。系统 MUST 继续明确标记该组合是 `research_combo_only`，而不是正式多 sleeve Governor 真相。

#### Scenario: unified combo 运行完成
- **WHEN** unified combo 完成一次运行并生成 `run_meta.json`
- **THEN** `run_meta` MUST 同时包含 `research_combo_only=true`
- **THEN** `run_meta` MUST 包含官方组件来源元数据，足以追溯 stock/ETF 两条腿各自的来源
