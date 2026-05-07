## Why

当前市场数据消费入口仍散落在 `pg_provider`、`universe resolver`、`market_snapshot_service` 和 runtime compile 链路里，并继续把 `data_role`、`pams_ohlcv_daily`、`v2_runtime` 当成并列入口使用。这与当前已经收口的数据库与系统文档冲突，且会持续阻塞前端、事务域和执行链的后续收敛。

## What Changes

- 新增统一 `market data access contract`，把价格历史、benchmark 历史、交易日历、PIT 成分、PIT 行业、证券主数据收敛到单一正式访问边界。
- 将 runtime compile 的正式市场数据入口收敛为 `canonical_market` source contract，不再以 `data_role`、`stocks_table`、`stocks_mapping_table` 作为正式上层合同。
- 调整 `universe resolver` 和 `market snapshot` 的正式要求，使其通过统一市场数据访问层消费 PIT 与行情，而不是各自直连底表。
- 调整 V2 runtime compat 治理口径，使 compat 层只保留为旧 baseline 迁移壳，不再被定义为长期正式默认消费层。
- 调整研究数据库结构治理口径，把核心研究表认知从“单表主路径”收敛到 `raw_source / pit_mapping / canonical_market` 三层。
- **BREAKING** 新增或重构后的正式主路径不得再把 `pams_ohlcv_daily`、`pams_ohlcv_daily_v2_runtime`、`data_role` 作为长期正式入口。

## Capabilities

### New Capabilities
- `market-data-access-contract`: 定义 `canonical_market` 之上的统一市场数据访问合同、能力面、输入维度和审计回显。

### Modified Capabilities
- `api-runtime-config-compilation`: runtime compile 的正式市场数据入口改为 `canonical_market` source contract，并限制 shadow source 只作为显式对照入口。
- `universe-resolver`: resolver 的正式市场数据与 PIT 消费边界改为统一访问层，不再以底表直查作为长期正式路径。
- `market-snapshot-daily`: 市场快照构建正式上改为通过统一市场数据访问层消费价格、日历与 PIT 数据。
- `cn-stock-v2-runtime-compat-governance`: compat 层降级为迁移期兼容壳，不再作为长期正式默认消费层。
- `research-db-structure-governance`: 研究数据库结构治理改为围绕三层市场数据域，而不再围绕 `pams_ohlcv_daily` 单表主路径。

## Impact

- 受影响代码主要位于：
  - `backend/core/data`
  - `backend/core/universe`
  - `backend/core/services/market_snapshot_service.py`
  - `backend/api/backtest_v2/runner_config_bundle.py`
  - `backend/core/config/models.py`
- 受影响的合同与规格包括：
  - runtime compile
  - universe 解析
  - market snapshot 构建
  - V2 runtime compat 治理
  - 研究数据库结构治理
- 受影响的验证面包括：
  - `baseline_V10.1` runtime compile 等价性
  - `universe resolver` PIT 行为一致性
  - market snapshot 构建结果与审计回显
