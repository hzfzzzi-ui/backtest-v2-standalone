## ADDED Requirements

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
