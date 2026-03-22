## Why

当前 `HS300_ZZ500` 依赖的 `000906.SH` 成分历史仍然走 `monthly` 重建加旧库 patch merge，这会把正式研究链稳定降级为 `mixed / approximate / warn`。既然后续正式数据源要切到 `Tushare`，就需要把 `CSI800` 的正式 PIT 链改成单源、非月度、可审计的历史变更链。

## What Changes

- 新增 `CSI800/000906.SH` 的正式 `Tushare` 历史抓取脚本，基于实际 `trade_date` 的成分集合变化重建 snapshots 和 changes。
- 扩展 `import_csi800_pit.py`，支持正式链的全量替换导入、结构化摘要输出和 source label 区分；旧的 patch merge 仅保留为兼容/近似路径。
- 更新 `refresh_csi800_pit.py` 和 `backend/core/universe/lineage.py`，让 `HS300_ZZ500` 的正式 lineage 指向新的 `Tushare` 历史链，旧月度脚本降为 fallback 说明。
- 补充单元测试和可复现命令，确保正式链不会再默认产出 `monthly` 或 `mixed` 口径。

## Capabilities

### New Capabilities
- `csi800-tushare-pit-history`: 定义 `000906.SH` 的正式 `Tushare` PIT 历史抓取与变更重建链。

### Modified Capabilities
- `universe-data-ingest`: 将 `CSI800` 成分导入从月度近似 patch 扩展为正式 `Tushare` 历史链加显式 fallback。
- `universe-resolver`: 扩展 `HS300_ZZ500` 的正式 lineage 元信息和导入入口，明确正式链与 fallback 链的边界。

## Impact

- 受影响代码主要包括 `backend/scripts/fetch_csi800_pit*.py`、`backend/scripts/import_csi800_pit.py`、`backend/cli/managed/refresh_csi800_pit.py`、`backend/core/universe/lineage.py` 和对应测试。
- 受影响数据路径主要包括 `data_cache/csi800_pit_*.csv`、`outputs/ops/csi800_pit_*_summary.json` 和数据库中的 `pit_index_constituents(index_code='000906.SH')`。
- 外部依赖将明确收敛到 `Tushare index_weight(index_code='000906.SH')`；旧月度脚本和 AKShare 静态链不再作为正式研究入口。
