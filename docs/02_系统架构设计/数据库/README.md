# 数据库文档入口

本目录描述当前数据库正式边界、访问约束与运行合同。

阅读顺序建议：
1. [数据库架构设计.md](./数据库架构设计.md)
2. [市场数据访问边界.md](./市场数据访问边界.md)
3. [pams_ohlcv_daily_v2_schema_contract.md](./pams_ohlcv_daily_v2_schema_contract.md)
4. [pams_ohlcv_daily_v2_runtime_contract.md](./pams_ohlcv_daily_v2_runtime_contract.md)
5. [v2_source_matrix.md](./v2_source_matrix.md)
6. [core_db_structure_l2_runbook.md](./core_db_structure_l2_runbook.md)
7. [pams_ohlcv_daily_v2_runbook.md](./pams_ohlcv_daily_v2_runbook.md)

当前数据库口径：
- 市场数据以 `canonical_market` 为正式消费面
- `runtime compat` 只在文档明确保留的边界内存在
- `outputs/` 不是数据库真相层
- 研究数据、业务数据、实验数据三域要保持逻辑隔离
