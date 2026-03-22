## Why

当前系统虽然已经暴露 `CSI1000` universe_mode，但运行时使用的 `000852.SH` 成分历史仍然主要依赖静态 fallback 或月度近似重建，不能稳定表达中证1000“半年定期调整并可能伴随临时调整”的真实 PIT 轨迹。这会直接污染股票池可比性，使 `CSI1000` 回测结果混入数据口径漂移，无法作为 baseline 级研究结论使用。

现在需要把 `CSI1000` 正式纳入研究主链，因此必须先补齐可审计的数据源、调样日历和运行前质量门禁，先解决“股票池是否可信”，再讨论策略在 `CSI1000` 上是否有效。

## What Changes

- 新增 `CSI1000` 正式 PIT 数据链，明确主数据源、调样日历、快照抓取、变更重建和导入协议。
- 新增 `CSI1000` 调样日历能力，支持按半年度定期调整生效日抓取，并为临时调整保留显式记录入口。
- 为 `CSI1000` 导入链增加来源标签、调样日历版本和质量统计，区分正式 PIT、月度近似、静态 fallback。
- 扩展现有 universe membership 审计门禁，把来源标签、形态特征与调样日历覆盖证据一起纳入判定，识别“全量静态快照伪装成 PIT 历史”等高风险数据形态。
- 扩展 universe resolver 与 lineage 对 `CSI1000` 的规范要求，要求向运行元信息和审计产物暴露足够的 lineage、日历版本与质量字段，便于前端和研究报告验证。
- 明确本次 change 不修改策略逻辑、不修改手续费/滑点/执行口径，不把收益优化与数据修复混在同一轮。

## Capabilities

### New Capabilities
- `csi1000-rebalance-calendar`: 定义中证1000调样生效日历及其来源、版本和维护要求，作为 PIT 快照抓取的唯一日历输入。
- `universe-membership-audit`: 定义指数成分历史在进入回测前必须通过的数据质量审计规则，并对静态 fallback、低保真近似数据发出阻断或告警。

### Modified Capabilities
- `universe-data-ingest`: 将现有指数成分导入能力从“CSI800 正式链路 + CSI1000 临时脚本”扩展为包含 `CSI1000` 正式 PIT 数据源、导入来源标签和可复核统计输出。
- `universe-resolver`: 将 resolver 能力从现有 `ALL_A / HS300_ZZ500 / INDUSTRY / CUSTOM` 口径扩展到正式支持 `CSI1000`，并要求输出与 `CSI1000` PIT 数据质量相关的 lineage 元信息。

## Impact

- 受影响代码主要包括 `backend/scripts/fetch_csi1000_pit*.py`、`backend/scripts/import_csi1000_pit.py`、`backend/core/universe/*`、`backend/core/tools/data_bundle_builder.py`、`backend/core/audit/*` 以及相关产物输出链路。
- 受影响数据系统包括 `pit_index_constituents` 和与 universe lineage 相关的 `run_meta.json` / `audit.json` 输出。
- 外部依赖将明确收敛到“中证官方调样规则 + Tushare 历史指数成分权重接口”为主，AKShare 静态成分仅保留为应急校验路径。
- 本次 change 为后续 `CSI1000` baseline 研究提供前置数据基础，但不直接改变任何现有 baseline 的收益指标口径。
