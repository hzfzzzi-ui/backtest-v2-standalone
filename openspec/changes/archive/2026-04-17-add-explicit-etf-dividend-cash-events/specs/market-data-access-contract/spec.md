## ADDED Requirements

### Requirement: 统一市场数据访问层 MUST 提供 ETF 分红事件读取
统一市场数据访问层 MUST 以正式业务能力暴露 `cn_etf` 分红事件，不得要求上层直接访问底表或自行拼接 Tushare 返回。

#### Scenario: cn_etf 主路径读取分红事件
- **WHEN** `asset_scope = "cn_etf"` 的 backtest / research 主路径构建 data bundle
- **THEN** 统一市场数据访问层返回窗口内相关 ETF 的分红事件集合
- **AND** 上层无需知道底表名

### Requirement: ETF 分红事件查询必须带审计回显
统一市场数据访问层 MUST 为 ETF 分红事件查询记录正式审计回显。

#### Scenario: provider 审计记录 dividend events 查询
- **WHEN** provider 读取 ETF 分红事件
- **THEN** query audit 记录命中的表、symbols、时间窗口与返回行数
- **AND** data bundle summary 暴露 dividend event 行数与覆盖窗口
