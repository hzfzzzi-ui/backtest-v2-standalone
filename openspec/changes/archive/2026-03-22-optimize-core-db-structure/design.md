## Context

当前数据库不是回测系统独占库，而是共享的 `pams` PostgreSQL 实例。实际 `public` schema 中共有 120 张表，其中 `pams_` / `pit_` 表 39 张，但当前回测主路径持续依赖的核心研究表只有：

- `pams_ohlcv_daily`
- `pit_index_daily`
- `pit_index_constituents`
- `pit_industry_history`
- `pit_security_master`
- `pit_st_history`

辅助但非 baseline 核心的表主要是：

- `pams_sentiment_state`
- `pams_transactions`
- `pams_transaction_sync_log`
- `pit_trade_cal`

当前已确认的结构问题有三类：

1. `pit_index_constituents` 缺少主键、唯一约束和索引，按 `index_code + 生效区间` 的主查询是顺序扫描。
2. `pit_industry_history` 虽然有主键和 `(ts_code, standard)` 索引，但按 `industry_l1 + 生效区间` 的主查询仍是顺序扫描。
3. `public` schema 中存在 `pams_holdings_snapshot_backup_20260215`、`pams_transactions_backup_20260215` 这类历史备份表，容易混淆核心表与一次性产物。

同时，需要明确以下约束：

- 不能改变 baseline_V10.1 的研究口径。
- 不能改变 Universe 结果集合、交易日历口径、信号与执行时点。
- 不能在没有显式 spec 的情况下把高风险结构改动混入一次“顺手优化”。

## Goals / Non-Goals

**Goals:**

- 固化一份“核心研究表最小化结构优化”方案，先解决最明确的索引缺口。
- 把可以直接实施的 L2 DDL 与必须单独立项的 L3 结构变更分开。
- 为每个 DDL 提供验证 SQL、回退 SQL 和风险提示，确保可审计、可回滚。
- 为备份/临时表建立治理边界，避免继续污染主 schema 认知。

**Non-Goals:**

- 不做 `pams_ohlcv_daily` 分区、拆表或迁移到新 schema。
- 不切换 `load_trading_calendar_cn()` 到 `pit_trade_cal`。
- 不修改 `pit_index_constituents` / `pit_industry_history` 的业务含义与 PIT 判定语义。
- 不修改任何 baseline 策略逻辑、执行逻辑、产物协议。
- 不处理 Firefly 或其他共享系统的非 `pams_` / `pit_` 表。

## Decisions

### D1: 先做“角色分层”，再做 DDL

本次 change 先把数据库对象分成四层：

- 核心研究表：`pams_ohlcv_daily`、`pit_index_daily`、`pit_index_constituents`、`pit_industry_history`、`pit_security_master`、`pit_st_history`
- 辅助研究表：`pams_sentiment_state`、`pit_trade_cal`
- 外围业务表：`pams_transactions`、`pams_transaction_sync_log` 及其他未进入回测主路径的 `pams_*`
- 历史备份/临时对象：`*_backup_*` 与脚本中的 `tmp_*` 会话表

这样做的原因是，当前最大的风险不是“DDL 太少”，而是“哪些表属于回测主线”没有边界。先定角色，后续 DDL 才能稳。

备选方案：

- 直接对所有 `pams_*` / `pit_*` 表统一做索引审计。
  不采用，因为范围过大，会把旁系业务表混入研究主线。

### D2: L2 只允许非语义型结构优化

L2 只包含不会改变查询结果集和研究口径的结构优化，具体限定为：

- 新增非唯一索引
- 补充 `COMMENT ON TABLE` / `COMMENT ON COLUMN`
- 输出 schema inventory / runbook
- 备份表治理清单

首批 L2 DDL 草案如下。

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pit_index_constituents_lookup
ON public.pit_index_constituents (index_code, start_date, end_date, symbol);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pit_industry_history_l1_lookup
ON public.pit_industry_history (industry_l1, start_date, end_date, ts_code);
```

可选的注释 DDL：

```sql
COMMENT ON TABLE public.pit_index_constituents IS
'研究主线核心表：指数成分 PIT 区间历史，供 universe_resolver 与 lineage 审计使用';

COMMENT ON TABLE public.pit_industry_history IS
'研究主线核心表：行业分类 PIT 区间历史，供行业 universe 与行业映射使用';
```

这样做的原因是：

- `pit_index_constituents` 当前主查询是 `index_code + start_date/end_date + symbol`，完全缺索引。
- `pit_industry_history` 当前主查询是 `industry_l1 + start_date/end_date + ts_code`，现有 `(ts_code, standard)` 索引不命中该模式。
- 这两个 DDL 不改变列值、不改变约束、不改变 provider 逻辑，属于最小改动。
- 对 `pit_index_constituents` 而言，即使新增索引，优化器仍可能因为表仅数千行而继续选择顺序扫描；这不自动构成失败，前提是实际耗时已被记录且不继续把 L2 推高到更激进结构改动。

备选方案：

- 给 `pams_ohlcv_daily` 增加 `(market, trade_date, symbol)` 复合索引。
  暂不纳入首批 L2。原因是表体量约 14.4M 行，写入成本更高，而且当前最重的 `ALL_A` 查询模式还需要先确认是否值得为 `DISTINCT symbol` 单独付出额外索引维护成本。

### D3: `pams_ohlcv_daily` 暂不进入首批 DDL 包

虽然 `ALL_A` Universe 构建会扫描 `pams_ohlcv_daily`，但这张表是当前最大表，也是写入最频繁的研究主表。首批结构优化不直接改它，只做如下约束：

- 保留现有主键和索引不变
- 先把 `EXPLAIN` 基线纳入 runbook
- 如后续需要新增复合索引，必须先给出写放大评估和导入脚本回归结果

备选方案：

- 直接补一个覆盖 `market='CN_A'` 的部分索引。
  暂不采用，因为当前没有足够证据说明这是“最小且确定收益”的改动。

### D4: L3 只保留为显式升级项

以下结构调整全部定义为 L3，本次只写 spec，不默认实施：

- 给 `pit_index_constituents` 增加主键或唯一约束
- 增加 `NOT NULL` 约束，例如要求 `start_date` 全量非空
- 引入区间重叠约束，禁止同一 `index_code + symbol` 出现冲突区间
- 把交易日历主来源从 `pams_ohlcv_daily` / `pit_index_daily` 切换到 `pit_trade_cal`
- 把研究主线表迁移到独立 schema，例如 `bt_research`
- 迁移或重命名 `*_backup_*` 持久表

这样分级的原因是，这些改动会影响写入合同、运行时数据来源、运维流程或共享库兼容性，已经超出“只做最小改动”的边界。

### D5: 验证与回退必须内建到 DDL 方案

每个 L2 DDL 必须配套三类验证：

1. 结构验证：确认索引存在
2. 查询验证：`EXPLAIN` 或 `EXPLAIN ANALYZE` 确认主查询不再走顺序扫描
3. 语义验证：行数、去重统计、关键结果集与变更前一致

对应回退方式统一要求为 `DROP INDEX CONCURRENTLY IF EXISTS ...`，不得使用破坏性回退。

推荐验证 SQL：

```sql
EXPLAIN
SELECT DISTINCT symbol
FROM public.pit_index_constituents
WHERE index_code = '000906.SH'
  AND start_date <= DATE '2026-03-01'
  AND (end_date IS NULL OR end_date > DATE '2026-03-01')
ORDER BY symbol;

EXPLAIN
SELECT DISTINCT ts_code
FROM public.pit_industry_history
WHERE industry_l1 IN ('银行', '非银金融')
  AND start_date <= DATE '2026-03-01'
  AND (end_date IS NULL OR end_date > DATE '2026-03-01')
ORDER BY ts_code;
```

回退 SQL：

```sql
DROP INDEX CONCURRENTLY IF EXISTS public.idx_pit_index_constituents_lookup;
DROP INDEX CONCURRENTLY IF EXISTS public.idx_pit_industry_history_l1_lookup;
```

## Risks / Trade-offs

- [共享库中仍有未知外部消费者] -> 只把首批 DDL 限制在新增索引和注释，避免破坏外部写入/读取合同。
- [新增索引会增加写入成本] -> 首批只改中小 PIT 表，不动 `pams_ohlcv_daily` 这种大写入表。
- [索引列顺序不匹配真实查询模式] -> 先以当前主路径 SQL 为准，并在实施前后保留 `EXPLAIN` 基线。
- [备份表移动可能影响未知脚本] -> `*_backup_*` 先做治理清单，不在本次直接移动。
- [把 `pit_trade_cal` 直接切为交易日历真源可能改变行为] -> 明确升级为 L3，单独做 spec 和回归。

## Migration Plan

1. 导出当前索引与 `EXPLAIN` 基线，保存到运维记录。
2. 在低峰期执行首批 L2 DDL：
   - `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pit_index_constituents_lookup`
   - `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pit_industry_history_l1_lookup`
3. 对相关表执行 `ANALYZE`。
4. 重新执行关键 `EXPLAIN`，确认不再走 `Seq Scan`。
5. 运行最小语义回归：
   - Universe resolver 对同一 `as_of` 的返回 symbol 集合不变
   - 行业列表 API 与行业映射结果不变
6. 如发现异常，使用 `DROP INDEX CONCURRENTLY` 回退。
7. 将 `*_backup_*` 持久表登记为治理债务，不在本次直接迁移。

## Open Questions

- `pit_index_constituents` 是否存在仓库外的写入方，未来是否需要真正的唯一约束或区间约束？
- `ALL_A` Universe 的性能瓶颈是否已经严重到需要为 `pams_ohlcv_daily` 增加额外复合索引？
- `pit_trade_cal` 是否准备在后续版本成为运行时标准交易日日历源？
- 共享 `public` schema 是否允许新增 `archive` schema，供未来备份表迁移？
