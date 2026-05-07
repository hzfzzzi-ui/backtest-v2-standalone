## ADDED Requirements

### Requirement: 统一市场数据访问层 MUST 作为正式市场数据唯一消费边界
系统 MUST 提供统一 `market data access contract` 作为正式市场数据消费边界。研究、回测、snapshot 与 universe 主路径 MUST 通过该合同消费 `canonical_market`，而 SHALL NOT 再把 `data_role`、`stocks_table`、`pams_ohlcv_daily` 或 `pams_ohlcv_daily_v2_runtime` 作为长期正式入口暴露给上层。

#### Scenario: 研究主路径消费价格历史
- **WHEN** 回测或研究主路径请求价格历史
- **THEN** 系统 MUST 通过统一市场数据访问层读取 `canonical_market`
- **THEN** 上层 SHALL NOT 继续直接选择 `pams_ohlcv_daily`、`pams_ohlcv_daily_v2` 或 compat 表名

### Requirement: 统一市场数据访问层 MUST 覆盖正式 L1 业务能力面
统一市场数据访问层 MUST 至少覆盖以下正式 `L1` 能力：价格历史、benchmark 历史、交易日历、PIT 成分、PIT 行业、证券主数据。各能力 MUST 按业务能力命名，而不是按底表命名。

#### Scenario: 请求正式能力
- **WHEN** 上层请求价格、benchmark、交易日历、PIT 或证券主数据
- **THEN** 统一访问层 MUST 以业务能力语义提供对应数据
- **THEN** 调用方 SHALL NOT 需要知道具体底表名或 schema mapping

### Requirement: 统一市场数据访问层 MUST 固定输入维度与审计回显
统一市场数据访问层 MUST 固定输入维度为 `asset_scope`、`market`、`data_level`、`as_of_date` 或 `window`、`symbols`。统一访问层 MUST 固定回显实际命中的 canonical 对象、时间窗口、市场、是否降级、是否缺数、查询版本、`cache_hit` 与 `cache_version`。

#### Scenario: 请求批量 PIT 成分快照
- **WHEN** 上层以 `asset_scope`、`market`、`data_level='L1'`、`as_of_date` 与目标对象请求 PIT 成分快照
- **THEN** 访问层 MUST 返回结果与固定审计回显
- **THEN** 若直接命中 canonical，回显 MUST 包含 `cache_hit=false` 与 `cache_version='direct_canonical'`

### Requirement: 统一市场数据访问层 MUST 固定最小输出字段
统一市场数据访问层 MUST 为正式能力返回固定最小字段集：价格历史与 benchmark 历史返回 `date / symbol / open / high / low / close / volume / amount / adj_factor / is_suspended`；PIT 成分返回 `index_code / symbol / start_date / end_date / as_of_date`；PIT 行业返回 `symbol / industry_l1 / industry_l2 / standard / start_date / end_date / as_of_date`；证券主数据返回 `symbol / ts_code / name / market / exchange / security_type / asset_scope / list_date / delist_date / is_active_at_asof`。

#### Scenario: 请求证券主数据
- **WHEN** 上层请求单标的或批量证券主数据
- **THEN** 返回结果 MUST 至少包含正式最小字段集
- **THEN** 系统 SHALL NOT 以缺失 `name` 或 `asset_scope` 的结构作为正式成功返回
