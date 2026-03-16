## 1. 基线盘点与治理边界

- [x] 1.1 固化研究主线表 inventory，DoD：形成核心/辅助/外围/备份四层清单并与当前实库一致；验证：逐表对照 `information_schema.tables` 与主路径代码引用；风险：共享库中存在仓库外消费者未被盘点。
- [x] 1.2 固化关键查询基线，DoD：记录 `pit_index_constituents`、`pit_industry_history`、`ALL_A` Universe 三类主查询的 `EXPLAIN` 输出；验证：保存执行 SQL 与计划文本；风险：不同统计信息窗口下执行计划会轻微波动。

## 2. L2 最小化 DDL 包

- [x] 2.1 生成 `pit_index_constituents` 索引 DDL 与回退 DDL，DoD：提供 `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pit_index_constituents_lookup` 与对应 `DROP INDEX CONCURRENTLY`；验证：`pg_indexes` 可见，且已记录该小表在约 5,934 行规模下仍由优化器选择 2ms 级顺序扫描的边界条件；风险：索引列顺序若与真实查询偏离，收益会不足。
- [x] 2.2 生成 `pit_industry_history` 索引 DDL 与回退 DDL，DoD：提供 `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pit_industry_history_l1_lookup` 与对应回退；验证：行业 universe 查询命中新索引且结果集不变；风险：如果行业筛选维度后续变化，索引收益会下降。
- [x] 2.3 补充表级注释与 runbook 说明，DoD：把核心表角色、执行顺序、验证步骤、回退步骤写入文档或 DDL 注释；验证：运维文档可独立复用；风险：只写 DDL 不写 runbook 会导致后续重复误判表角色。
- [x] 2.4 完成 L2 语义回归，DoD：同一 `as_of` 下 Universe symbol 集合、行业列表、ST 历史读取结果与变更前一致；验证：执行主路径查询或脚本比对行数/集合差异；风险：如果回归样本窗口太短，可能遗漏边缘日期问题。

## 3. L3 延后项与独立升级准备

- [x] 3.1 对 `pit_index_constituents` 约束增强单独立项，DoD：在 `docs/db/core_db_structure_l3_followups.md` 中单独审计主键、唯一约束、`start_date NOT NULL`、区间冲突约束的历史脏数据与外部写入方，并给出候选 change 名称与约束 DDL；验证：重复/空值/区间重叠审计结果已落文；风险：直接上约束可能阻塞导入脚本或共享库写入。
- [x] 3.2 对 `pit_trade_cal` 运行时切换单独立项，DoD：在 `docs/db/core_db_structure_l3_followups.md` 中形成交易日日历真源切换的独立项边界，明确与现有 `pams_ohlcv_daily` / `pit_index_daily` 的口径对比结果；验证：同一时间窗交易日序列逐日差异已审计为 0；风险：切换后仍可能改变运行时回退路径与历史口径。
- [x] 3.3 对持久化备份表迁移单独立项，DoD：在 `docs/db/core_db_structure_l3_followups.md` 中明确 `*_backup_*` 表的治理候选方案、目标 change 名称与当前代码引用现状；验证：备份表不再被误判为核心研究表；风险：未知脚本可能仍在直接读取这些表。
