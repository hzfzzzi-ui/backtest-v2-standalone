# 核心研究表 L3 Follow-ups

本文件不执行任何 DDL，只把不适合并入本轮 L2 的结构升级拆成独立后续项。

## 1. `harden-pit-constraint-contracts`

### 当前事实

- `pit_index_constituents` 目前没有主键和唯一约束。
- 已审计结果：
- `(index_code, symbol, start_date)` 重复数：`0`
- `start_date IS NULL` 行数：`0`
- 同一 `index_code + symbol` 的区间重叠数：`0`
- 外部写入方是否仅限当前仓库脚本：`未知`

### 候选约束 DDL

```sql
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_pit_index_constituents_start
ON public.pit_index_constituents (index_code, symbol, start_date);
```

后续如确认写入合同稳定，再评估：

```sql
ALTER TABLE public.pit_index_constituents
  ADD CONSTRAINT pit_index_constituents_start_not_null
  CHECK (start_date IS NOT NULL) NOT VALID;
```

### 为什么属于 L3

- 会改变写入合同
- 可能影响导入脚本和仓库外写入方
- 一旦补区间约束，复杂度会显著上升

## 2. `switch-runtime-trade-calendar-source`

### 当前事实

对 `2016-01-01` 到 `2026-02-13` 的审计结果：

- `pit_trade_cal(exchange='SSE', is_open=true)` 交易日数：`2460`
- `pams_ohlcv_daily(market='CN_A')` 去重交易日数：`2460`
- `pit_index_daily(index_code='000300.SH')` 去重交易日数：`2460`
- `pit_trade_cal - pams_ohlcv_daily` 差异日数：`0`
- `pams_ohlcv_daily - pit_trade_cal` 差异日数：`0`
- `pit_trade_cal - pit_index_daily` 差异日数：`0`
- `pit_index_daily - pit_trade_cal` 差异日数：`0`

### 结论

从已审计窗口看，`pit_trade_cal` 与当前价格表导出的交易日序列一致，具备成为运行时真源的候选条件。

### 为什么属于 L3

- 会改变运行时“谁是真源”的合同
- 即使日历序列一致，也需要验证边界行为是否完全一致，例如上一交易日回退逻辑
- 一旦切换，需要回归所有依赖交易日历的入口

## 3. `govern-persistent-backup-tables`

### 当前事实

| 表名 | 估计行数 | 总大小（bytes） | 代码引用 |
| --- | ---: | ---: | --- |
| `pams_holdings_snapshot_backup_20260215` | 0 | 16384 | 未发现 |
| `pams_transactions_backup_20260215` | 0 | 16384 | 未发现 |

说明：

- 这两张表当前在 `pg_stat_user_tables` 中估计行为 `0`，但历史行数盘点曾出现过小规模数据。
- 在当前仓库的 `backend/`、`frontend/`、`research/`、`tests/` 路径下未发现显式代码引用。

### 候选治理动作

1. 迁移到独立 `archive` schema。
2. 导出为离线快照后删除。
3. 保留但补 owner / created_at / retention 说明。

### 为什么属于 L3

- 会影响共享库运维边界
- 可能涉及仓库外人工流程
- 不应在未确认保留策略前直接删除

## 4. 建议顺序

1. 先做 `harden-pit-constraint-contracts` 的写入方盘点。
2. 再做 `switch-runtime-trade-calendar-source` 的运行时回归。
3. 最后处理 `govern-persistent-backup-tables` 的迁移或清理。
