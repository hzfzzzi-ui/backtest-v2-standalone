# CSI1000 官方公告人工 ETL 方案

## 1. 目标

在没有 `Tushare index_weight` 或 `JQData get_index_stocks` 全历史权限时，使用 **中证指数官方样本调整公告/附件** 手工构建 `CSI1000 (000852.SH)` 的 PIT 成分历史。

这条链路的目标不是“自动抓最新快照”，而是：

1. 保证 `000852.SH` 的成分历史是 **多期 PIT**，不是单一静态快照。
2. 保证导入后能满足主线研究的 `PIT_DYNAMIC` 口径。
3. 让后续 `baseline_V9.1 -> CSI1000` 单变量对照具备严格可比性。

## 2. 适用场景

适用于以下情况：

- 无法获得 `Tushare index_weight(000852.SH)` 历史权限
- 无法获得 `JQData get_index_stocks('000852.XSHG', date=...)` 的 2016~2026 全历史权限
- 仍希望以官方公告为原始依据，自建可信 PIT 历史

## 3. 原始资料

优先使用：

1. 中证指数官网的 **样本股调整公告 / 调整名单附件**
2. 中证指数官网的 **成分股名单附件（xls/xlsx/csv/pdf 导出的 csv）**

建议按“**每次调整生效日** 一期快照”的粒度准备文件。

## 4. 目录与输入格式

### 4.1 快照文件

每个官方快照文件可以是：

- `.csv`
- `.xls`
- `.xlsx`

文件内只要存在一个可识别的代码列即可。支持常见列名：

- `symbol`
- `code`
- `con_code`
- `证券代码`
- `股票代码`
- `样本代码`
- `成分股代码`

如果列名不标准，脚本会尝试自动识别“绝大部分是 6 位证券代码”的列。

### 4.2 manifest 文件

需要准备一个 manifest CSV，例如：

```csv
effective_date,snapshot_path,source,source_url,source_note
2016-03-01,snapshots/2016-03-01.csv,csindex_notice,https://example.com/notice1,定期调整
2016-09-01,snapshots/2016-09-01.xlsx,csindex_notice,https://example.com/notice2,定期调整
```

字段说明：

- `effective_date`：该期快照的生效日，必填，`YYYY-MM-DD`
- `snapshot_path`：快照文件路径，支持相对 manifest 的相对路径
- `source`：数据血缘标签，建议填 `csindex_notice`
- `source_url`：公告或附件链接，可选
- `source_note`：备注，可选

## 5. 生成 PIT changes

脚本：

- [build_csi1000_pit_from_manual_snapshots.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/build_csi1000_pit_from_manual_snapshots.py)

运行示例：

```powershell
python backend/scripts/build_csi1000_pit_from_manual_snapshots.py `
  --manifest data_cache/csi1000_manual/manifest.csv `
  --out-dir data_cache/csi1000_manual
```

默认约束：

- 每期成分数应为 `1000`
- 若某期不是 `1000`，脚本会直接报错

如确有官方临时调整期不是整 `1000` 只，可临时放宽：

```powershell
python backend/scripts/build_csi1000_pit_from_manual_snapshots.py `
  --manifest data_cache/csi1000_manual/manifest.csv `
  --out-dir data_cache/csi1000_manual `
  --allow-count-mismatch
```

输出文件：

- `csi1000_pit_manual_snapshots.csv`
- `csi1000_pit_manual_changes.csv`

其中 `changes.csv` 字段为：

- `index_code`
- `symbol`
- `in_date`
- `out_date`
- `source`

## 6. 导入数据库

脚本：

- [import_csi1000_pit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/import_csi1000_pit.py)

运行示例：

```powershell
python backend/scripts/import_csi1000_pit.py `
  --from-csv data_cache/csi1000_manual/csi1000_pit_manual_changes.csv `
  --source-label csindex_notice
```

行为：

- 只删除 `index_code='000852.SH'`
- 不会动其他指数 PIT 数据

## 7. 导入后验收

至少检查：

1. `000852.SH` 不再只有单一 `start_date`
2. `source` 不再是 `akshare_csi1000_static`
3. `distinct start_date` 应明显大于 `1`
4. `active` 成分数在当前日期附近应接近 `1000`

建议 SQL：

```sql
select
  count(*) as rows,
  count(distinct start_date) as distinct_start_dates,
  count(distinct source) as distinct_sources
from pit_index_constituents
where index_code = '000852.SH';
```

```sql
select source, count(*)
from pit_index_constituents
where index_code = '000852.SH'
group by source
order by count(*) desc;
```

## 8. 审计注意事项

### 8.1 只认生效日，不认公告日猜测

如果公告里同时给出“公告日”和“调整生效日”，manifest 里的 `effective_date` 必须写 **生效日**。

### 8.2 不要从当前名单倒推历史

禁止用最新 `CSI1000` 名单复制回过去月份。  
这只会重现当前已证伪的静态快照问题。

### 8.3 PDF 转表后要做代码归一化

脚本会把 `000001` 归一化为 `000001.SZ`，把 `600000` 归一化为 `600000.SH`。  
但如果 PDF OCR 出错成非 6 位代码，仍需要人工修正源文件。

### 8.4 允许人工 ETL，但必须保留血缘

manifest 里的 `source_url / source_note` 建议始终保留，便于后续抽查。

## 9. 当前结论

在当前权限条件下，这条“官方公告人工 ETL”路线是 **可执行的备选正式修复方案**。  
它不是最快的，但比继续使用静态 `AkShare` 快照更可信。

如果后续拿到 `Tushare` 或 `JQData` 全历史权限，仍建议优先切回自动月度 PIT 数据源。
