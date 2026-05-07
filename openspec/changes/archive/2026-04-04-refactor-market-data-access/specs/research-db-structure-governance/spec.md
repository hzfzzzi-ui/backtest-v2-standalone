## MODIFIED Requirements

### Requirement: 核心研究表结构治理分层
系统 MUST 对共享 PostgreSQL `public` schema 中的数据库对象进行分层治理，并将研究主线数据库优化与正式边界认知收敛到市场数据域的三层主路径：`raw_source`、`pit_mapping`、`canonical_market`。核心研究数据库对象 MUST 围绕这三层识别，而不再把 `pams_ohlcv_daily` 视为长期正式主路径。

#### Scenario: 识别核心研究层
- **WHEN** 团队制定或评审回测系统数据库结构优化方案
- **THEN** 方案 MUST 将 `raw_source`、`pit_mapping` 与 `canonical_market` 识别为正式研究主路径
- **THEN** `pams_ohlcv_daily` MUST 被视为历史迁移对象，而不是长期正式核心研究表

#### Scenario: 识别旧 compat 与历史对象
- **WHEN** 团队盘点历史 `v1`、compat view 或旧脚本依赖对象
- **THEN** 这些对象 MUST 被标记为迁移期兼容壳或历史对象
- **THEN** 团队 SHALL NOT 再把它们写入新的正式数据库主路径定义
