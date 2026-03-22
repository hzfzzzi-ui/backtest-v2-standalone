## ADDED Requirements

### Requirement: Universe resolver 必须正式支持 CSI1000 历史成分口径
系统 MUST 将 `CSI1000` 视为正式支持的指数股票池模式，并在 `PIT_DYNAMIC` 口径下使用 `pit_index_constituents` 中 `index_code='000852.SH'` 的历史成分记录，而不是把它视作临时脚本输出。

#### Scenario: 解析中证1000历史成分
- **WHEN** `universe_mode='CSI1000'` 且 `membership_mode='PIT_DYNAMIC'`
- **THEN** resolver 或其上游数据加载链路 MUST 从 `pit_index_constituents` 的 `000852.SH` 历史记录生成成分并集和 membership history

#### Scenario: 缺失历史成分时报错
- **WHEN** `CSI1000` 的 `PIT_DYNAMIC` 请求缺少有效历史成分记录
- **THEN** 系统 MUST 返回可审计的错误或告警
- **THEN** 系统 MUST 不得静默回退到最新静态成分

### Requirement: CSI1000 resolver 元信息必须暴露 lineage 与质量字段
系统 MUST 为 `CSI1000` 的 resolver/data bundle 输出足够的 lineage 和质量元信息，以便研究者判断该 universe 是否具备 PIT 可信度。

#### Scenario: 输出中证1000 lineage 元信息
- **WHEN** 回测使用 `CSI1000` 股票池
- **THEN** `run_meta.json` 或等价元信息 MUST 包含 `index_code`、`membership_mode`、`membership_history_rows`、`union_symbol_count`、`membership_source` 和 `membership_data_quality`

#### Scenario: 标记动态成分门控模式
- **WHEN** `CSI1000` 使用历史成分门控
- **THEN** 元信息 MUST 显式标记 `historical_membership_dynamic=true`
- **THEN** 元信息 MUST 显式标记当前过滤模式为基于动态成分的门控，而不是静态预过滤
