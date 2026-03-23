## Why

当前 `CSI1000` 导入链只把相邻快照重建成 `pit_index_constituents` 区间行，缺少“每个刷新日看到过哪些成分”的 refresh 级证据，导致零差异 refresh、临时非 PIT 刷新日和实际 `Tushare trade_date` 都无法被数据库长期保存。与此同时，实测 `Tushare index_weight(000852.SH)` 当前最早只到 `2015-07-31`，所以本次实现口径应明确收敛为 `2015-2026` 的 Tushare-covered PIT，并把更早空窗显式保留为 uncovered truth。

## What Changes

- 新增 `CSI1000` PIT refresh 侧表，按每个 refresh 日期保存 `symbol -> 主 PIT 区间行` 的映射，而不是只保留区间变化结果。
- 扩展 `CSI1000` 抓取/构建链路，显式输出 refresh 级 snapshots、`snapshot_trade_date` 和事件类型，保留 scheduled 与 ad_hoc/non-PIT refresh 记录。
- 扩展 `CSI1000` 导入链路，在同一事务内重建 `pit_index_constituents(000852.SH)` 与 refresh 侧表，并对零差异 refresh 继续落证。
- 修改成员历史审计逻辑，显式暴露 `Tushare` 覆盖下限与 pre-floor 未覆盖区间，禁止把该空窗误标成 formal PIT。

## Capabilities

### New Capabilities
- `csi1000-pit-refresh-sidecar`: 定义 `CSI1000` refresh 级成员快照侧表、主表映射规则和零差异 refresh 的保留口径。

### Modified Capabilities
- `csi1000-rebalance-calendar`: 调整日历必须允许 scheduled 与 ad_hoc/non-PIT refresh 共存，并保留“无成分差异但有 refresh 证据”的事件。
- `universe-data-ingest`: `CSI1000` Tushare 导入链必须同时产出区间主表和 refresh 侧表，并显式暴露 `Tushare` 覆盖下限。
- `universe-membership-audit`: 成员历史审计必须消费 refresh 侧表证据，并把 `2015-07-31` 之前的无源空窗维持为 uncovered/approximate，而不是伪装成 formal PIT。

## Impact

- 数据抓取/构建：`backend/cli/managed/fetch_csi1000_pit_by_calendar.py`、`backend/scripts/build_csi1000_pit_from_manual_snapshots.py`
- 数据导入：`backend/scripts/import_csi1000_pit.py`、`backend/cli/managed/refresh_csi1000_pit.py`
- 数据消费与审计：`backend/core/universe/membership_audit.py`、必要时 `backend/core/data/pg_provider.py`
- 数据库与文档：`docs/db/*`、新侧表 schema/apply SQL
- 测试：`tests/unit/test_fetch_csi1000_pit_by_calendar.py`、`tests/unit/test_import_csi1000_pit.py`、`tests/unit/test_refresh_csi1000_pit.py`、`tests/unit/test_research_audit_contract.py`
