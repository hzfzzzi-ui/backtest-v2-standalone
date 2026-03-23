## 1. 数据合同与 schema

- [x] 1.1 设计并落地 `CSI1000` refresh 侧表 schema 与索引，DoD：存在按 `index_code + refresh_date + symbol` 去重的侧表与查询索引；验证：schema/apply SQL 与导入单测；风险：主表无 surrogate key，只能依赖自然键映射。
- [x] 1.2 扩展 snapshots 数据合同，显式加入 `snapshot_trade_date` 与 refresh lineage 字段，DoD：Tushare 与 manual 两条链都能输出结构化 snapshots CSV；验证：`test_fetch_csi1000_pit_by_calendar.py`、`test_build_csi1000_pit_from_manual_snapshots.py`；风险：旧 CSV 读写兼容。

## 2. 导入与刷新链路

- [x] 2.1 扩展 `import_csi1000_pit.py`，在单事务内同时重建主区间表和 refresh 侧表，DoD：`000852.SH` 主表与侧表一起 replace import，并能对零差异 refresh 落证；验证：`test_import_csi1000_pit.py`；风险：snapshot row 映射不到主表区间时需要显式失败。
- [x] 2.2 扩展 `refresh_csi1000_pit.py` 与 summary 输出，DoD：refresh summary 同时暴露 `changes_csv`、`snapshots_csv`、`provider_floor_date` 与 sidecar 统计；验证：`test_refresh_csi1000_pit.py`；风险：旧 summary 消费方兼容。

## 3. 审计与验证

- [x] 3.1 扩展 `membership_audit`，把 refresh 侧表证据和 `provider_floor_date` 纳入 `CSI1000` 质量分类，DoD：covered window 与 pre-floor uncovered window 会得到不同审计结论；验证：`test_research_audit_contract.py` 与 membership audit 单测；风险：误把 `2012-2015` 空窗升格为 formal。
- [x] 3.2 跑最小回归并记录回退面，DoD：`CSI1000` 相关抓取/导入/审计测试通过，且能说明未改变 A 股现有 `CSI800/HS300_ZZ500` 口径；验证：pytest 定向回归与 summary 对比；风险：旧 `CSI1000` provisional 测试夹具掩盖真实回归。
