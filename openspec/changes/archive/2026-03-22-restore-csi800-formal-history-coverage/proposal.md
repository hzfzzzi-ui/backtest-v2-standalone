## Why

当前 `CSI800/000906.SH` 正式 refresh 已切到 `Tushare trade_date` 抓取，但实测远端只返回 `2025-08` 之后的完整 800 成分集合，直接 `--replace-existing` 会把原先覆盖 `2007+` 的长历史误替换成短历史，导致 `baseline_V10.1` 无法复现且 `universe_lineage` 继续停在 `WARN`。现在需要把长历史恢复能力、正式链物化和覆盖校验补齐，先保证研究主线可用，再保留后续 `Tushare` 增量更新入口。

## What Changes

- 新增 `CSI800` 正式历史链物化步骤，支持用单源长历史 seed 恢复 `2007+` 覆盖，并可按需叠加 `Tushare` 尾部变更后再做全量替换。
- 扩展 `refresh_csi800_pit.py`，在正式导入前校验覆盖范围；若抓取结果不能覆盖所需起点且未提供 seed，MUST 终止导入而不是误覆盖数据库。
- 更新 `HS300_ZZ500` formal lineage 文案和运维入口，明确正式链是“长历史 seed/正式链物化 -> replace import”，`Tushare trade_date` 仅作为可审计尾部更新来源，不再等同于单独可用的全历史链。
- 补充单测和 Docker 复审验证，确保恢复后 `baseline_V10.1` 能回到可复现状态，并给出新的 `universe_lineage` 结果。

## Capabilities

### New Capabilities

- `csi800-formal-history-materialization`: 物化可覆盖 `2007+` 的 `CSI800` 正式历史链，并输出结构化 provenance/coverage 摘要。

### Modified Capabilities

- `universe-data-ingest`: `CSI800` 正式 refresh 需要覆盖校验、seed 恢复和全量替换保护。
- `universe-resolver`: `HS300_ZZ500` formal lineage 需要改为指向“正式历史链物化”而不是“裸 `Tushare` 抓取结果”。

## Impact

- 受影响代码包括 `backend/scripts/import_csi800_pit.py`、`backend/cli/managed/refresh_csi800_pit.py`、新增正式链物化脚本、`backend/core/universe/lineage.py` 和对应测试。
- 受影响运维产物包括 `data_cache/csi800_*_changes.csv`、`outputs/ops/csi800_*_summary.json` 以及 `pit_index_constituents(index_code='000906.SH')`。
- Docker 数据库会执行一次 `000906.SH` 全量恢复与重审，需要显式记录恢复来源和回退路径。
