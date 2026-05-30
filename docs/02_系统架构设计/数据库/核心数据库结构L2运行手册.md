# 核心研究表 L2 结构优化 Runbook

## 1. 目标

本 runbook 只覆盖“最小改动、不碰研究口径”的 L2 数据库结构优化：

- 固化研究主线表 inventory
- 固化关键查询 `EXPLAIN` 基线
- 为 `pit_index_constituents`、`pit_industry_history` 增加非语义型索引
- 给出验证与回退步骤

不包含：

- 主键/唯一/非空/区间约束增强
- `pit_trade_cal` 运行时切换
- schema 拆分、迁移、分区

## 2. 研究主线表 Inventory

盘点日期：`2026-03-16`

### 2.1 核心研究表

| 表名 | 角色 | 当前行数 | 备注 |
| --- | --- | ---: | --- |
| `pams_ohlcv_daily` | 价格主表 | 14,414,560 | baseline 主价格源，当前不纳入首批 DDL |
| `pit_index_daily` | 指数日线 PIT 表 | 152,473 | benchmark / 行业指数读取 |
| `pit_index_constituents` | 指数成分 PIT 表 | 5,934 | Universe resolver 热路径 |
| `pit_industry_history` | 行业历史 PIT 表 | 12,717 | Universe resolver / 行业映射热路径 |
| `pit_security_master` | 证券主数据 | 5,812 | `ALL_A` Universe 依赖 |
| `pit_st_history` | ST 历史 PIT 表 | 811 | 过滤与审计依赖 |

### 2.2 辅助研究表

| 表名 | 角色 | 当前行数 | 备注 |
| --- | --- | ---: | --- |
| `pit_trade_cal` | 交易日历备选源 | 7,832 | 已落库，当前运行时未接入 |
| `pams_sentiment_state` | 市场快照辅助表 | 27 | 仅快照服务直接读取 |

### 2.3 外围业务表

| 表名 | 角色 | 当前行数 | 备注 |
| --- | --- | ---: | --- |
| `pams_transactions` | 外围交易接口表 | 28 | 不属于 baseline 研究主线 |
| `pams_transaction_sync_log` | 外围交易同步日志 | 8 | 仅事务接口清理使用 |

### 2.4 历史备份/临时对象

| 对象 | 类型 | 当前行数 | 备注 |
| --- | --- | ---: | --- |
| `pams_holdings_snapshot_backup_20260215` | 持久化备份表 | 31 | 非主线 |
| `pams_transactions_backup_20260215` | 持久化备份表 | 33 | 非主线 |
| `tmp_*` | 会话级临时表 | 不常驻 | 由脚本 `ON COMMIT DROP` 创建 |

## 3. 基线查询与优化理由

### 3.1 `pit_index_constituents` 热查询

用途：

- `HS300_ZZ500` / `CSI1000` Universe 解析
- 成分历史读取

基线 SQL：

```sql
EXPLAIN
SELECT DISTINCT symbol
FROM public.pit_index_constituents
WHERE index_code = '000906.SH'
  AND start_date <= DATE '2026-03-01'
  AND (end_date IS NULL OR end_date > DATE '2026-03-01')
ORDER BY symbol;
```

执行前基线：

```text
Unique
  -> Sort
       Sort Key: symbol
       -> Seq Scan on pit_index_constituents
            Filter: ((start_date <= '2026-03-01'::date) AND ((end_date IS NULL) OR (end_date > '2026-03-01'::date)) AND ((index_code)::text = '000906.SH'::text))
```

结论：当前为顺序扫描，且该表没有任何索引或约束。

### 3.2 `pit_industry_history` 热查询

用途：

- 行业 Universe 解析
- 行业映射历史读取

基线 SQL：

```sql
EXPLAIN
SELECT DISTINCT ts_code
FROM public.pit_industry_history
WHERE industry_l1 IN ('银行', '非银金融')
  AND start_date <= DATE '2026-03-01'
  AND (end_date IS NULL OR end_date > DATE '2026-03-01')
ORDER BY ts_code;
```

执行前基线：

```text
Unique
  -> Sort
       Sort Key: ts_code
       -> Seq Scan on pit_industry_history
            Filter: (((industry_l1)::text = ANY ('{银行,非银金融}'::text[])) AND (start_date <= '2026-03-01'::date) AND ((end_date IS NULL) OR (end_date > '2026-03-01'::date)))
```

结论：现有 `(ts_code, standard)` 索引不匹配按行业筛选的主查询模式。

### 3.3 `ALL_A` Universe 查询

基线 SQL：

```sql
EXPLAIN
WITH available AS (
  SELECT DISTINCT symbol
  FROM public.pams_ohlcv_daily
  WHERE market = 'CN_A'
    AND trade_date <= DATE '2026-03-01'
)
SELECT DISTINCT sm.symbol AS symbol
FROM public.pit_security_master sm
JOIN available a ON a.symbol = sm.symbol
WHERE sm.market_type = 'CN_A'
  AND sm.exchange IN ('SH', 'SZ')
  AND (sm.list_date IS NULL OR sm.list_date <= DATE '2026-03-01')
  AND (sm.delist_date IS NULL OR sm.delist_date > DATE '2026-03-01')
ORDER BY sm.symbol;
```

执行前基线结论：

- `pams_ohlcv_daily` 仍会出现 `Parallel Seq Scan`
- 这张表约 `4.97 GB`，写入频率高
- 本轮 L2 不直接加新索引，避免把大表写放大和口径验证一起绑入同一轮

## 4. DDL

apply 文件：`docs/db/core_db_structure_l2_apply.sql`

rollback 文件：`docs/db/core_db_structure_l2_rollback.sql`

本轮实际 DDL：

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pit_index_constituents_lookup
ON public.pit_index_constituents (index_code, start_date, end_date, symbol);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pit_industry_history_l1_lookup
ON public.pit_industry_history (industry_l1, start_date, end_date, ts_code);
```

## 5. 执行步骤

1. 确认连接目标为 `pams` 数据库，且拥有建索引权限。
2. 在无显式事务块下执行 apply SQL。
3. 对两张表执行 `ANALYZE`。
4. 用同一批 `EXPLAIN` 复核执行计划。
5. 用语义回归 SQL 校验结果集不变。

## 6. 验证步骤

### 6.1 结构验证

```sql
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
    'idx_pit_index_constituents_lookup',
    'idx_pit_industry_history_l1_lookup'
  )
ORDER BY tablename, indexname;
```

### 6.2 计划验证

重新执行第 3 节中的两条 `EXPLAIN`。

目标：

- `pit_industry_history` 应命中新索引
- `pit_index_constituents` 若仍顺序扫描，需要记录表规模与实际耗时，确认是否属于优化器对小表的理性选择

本次实际观测：

`pit_index_constituents`

```text
Unique  (actual time=2.032..2.169 rows=800)
  -> Sort
       -> Seq Scan on pit_index_constituents
            Rows Removed by Filter: 5134
Execution Time: 2.270 ms
```

结论：索引已成功创建，但由于表仅 5,934 行、目标结果约 800 行，优化器仍选择 2ms 级顺序扫描。该行为记录为“小表顺扫边界”，不升级为更激进 DDL。

`pit_industry_history`

```text
Bitmap Heap Scan on pit_industry_history  (actual time=0.099..0.465 rows=137)
  -> Bitmap Index Scan on idx_pit_industry_history_l1_lookup
Execution Time: 0.714 ms
```

结论：行业 Universe 热查询已明确命中新索引。

### 6.3 语义回归

`pit_index_constituents`：

```sql
SELECT COUNT(*)
FROM (
  SELECT DISTINCT symbol
  FROM public.pit_index_constituents
  WHERE index_code = '000906.SH'
    AND start_date <= DATE '2026-03-01'
    AND (end_date IS NULL OR end_date > DATE '2026-03-01')
) t;
```

`pit_industry_history`：

```sql
SELECT COUNT(*)
FROM (
  SELECT DISTINCT ts_code
  FROM public.pit_industry_history
  WHERE industry_l1 IN ('银行', '非银金融')
    AND start_date <= DATE '2026-03-01'
    AND (end_date IS NULL OR end_date > DATE '2026-03-01')
) t;
```

`pit_st_history`：

```sql
SELECT ts_code, start_date, end_date, st_type
FROM public.pit_st_history
WHERE ts_code = ANY(ARRAY['600000.SH','000001.SZ'])
  AND start_date <= DATE '2026-03-15'
  AND (end_date >= DATE '2026-03-01' OR end_date IS NULL)
ORDER BY ts_code, start_date;
```

本次实际回归结果：

- `HS300_ZZ500` Universe 代码路径返回 `800` 个 symbol
- `pit_index_constituents` 同条件 SQL 返回 `800` 个去重 symbol
- `pit_industry_history` 当前共有 `35` 个去重 `industry_l1`
- `pit_st_history` 在 `600000.SH` / `000001.SZ` 的给定窗口返回 `0` 行
- `load_index_constituent_history('000906.SH', 2026-01-01, 2026-03-01)` 代码路径返回 `850` 行、`850` 个去重 symbol

## 7. 回退步骤

1. 执行 rollback SQL。
2. 重新执行 `EXPLAIN`，确认计划回到变更前状态。
3. 重新检查 `pg_indexes`，确认新索引已消失。

## 8. 风险

- 共享库仍可能存在仓库外消费者，本 runbook 无法证明它们不存在。
- 新索引会引入轻微写入成本，但本轮只改中小 PIT 表。
- `ALL_A` Universe 性能问题本轮未处理，保留为后续独立评估项。

## 9. 延后到 L3 的项

- `pit_index_constituents` 主键 / 唯一 / 非空 / 区间重叠约束
- `pit_trade_cal` 运行时切换
- `*_backup_*` 持久化备份表迁移或清理
