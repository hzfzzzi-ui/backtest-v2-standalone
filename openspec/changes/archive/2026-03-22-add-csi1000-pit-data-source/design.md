## Context

当前系统已经在运行链路中暴露了 `CSI1000` universe_mode，并在 `data_bundle_builder` / `universe_resolver` 中把它映射到 `pit_index_constituents.index_code='000852.SH'`。但当前仓库中的 `CSI1000` 数据链存在三个结构性问题：

- 数据源分裂：既有静态 fallback，也有月度近似重建，缺少正式主源。
- 调样事件缺失：系统没有把中证1000的半年度定期调整和临时调整建模成显式事件日历。
- 运行前门禁仍不完整：当前代码虽然已经能基于来源标签和历史形态识别 `static_fallback / approximate / pit_verified`，并对 `CSI1000 + PIT_DYNAMIC + static_fallback` 做阻断，但还没有把调样日历版本、覆盖缺口和正式 lineage 证据纳入正式 PIT 判定。

这次变更的目标不是优化策略收益，而是把 `CSI1000` 变成一个可审计、可复现、可被前端和研究报告验证的数据输入能力。设计必须遵守当前项目的唯一真相原则：前端/配置声明的 `universe_mode=CSI1000`，后端必须能解释出它到底用了什么成分历史、什么质量等级，以及为什么可信或不可信。

## Goals / Non-Goals

**Goals:**
- 为 `CSI1000` 建立一条正式 PIT 数据链，主源明确、快照日历明确、导入口径明确。
- 把 `CSI1000` 的调样逻辑从“默认月度近似”改成“日历驱动的事件采样”。
- 在运行前加入 universe membership 质量分类与阻断门禁，防止静态 fallback 混入正式研究。
- 将 `CSI1000` 的来源、质量和动态成分元信息暴露到 `run_meta.json` 及相关审计输出。

**Non-Goals:**
- 不在本次变更中调整任何策略参数、排序逻辑、退出逻辑或仓位逻辑。
- 不在本次变更中引入新的 benchmark 规则或修改 `benchmark_regime` 行为。
- 不在本次变更中评估 `CSI1000` 相对 `HS300_ZZ500` 的收益优劣。
- 不把所有指数数据源统一重构；本次仅聚焦 `CSI1000`。

## Decisions

### 决策 1：`CSI1000` 正式历史源选用 Tushare，AKShare 仅保留为应急/校验
- 选择：正式 PIT 快照主源使用 `Tushare index_weight(index_code='000852.SH')`。
- 原因：当前候选源里，Tushare 最接近“可编程、可追溯、可覆盖历史事件”的要求；AKShare 现有接口更像最新静态成分，不适合作为 baseline 级历史主源。
- 备选：
  - 继续沿用 AKShare 静态成分：实现最省事，但审计不可通过。
  - 继续按月从 Tushare 近似重建：比静态好，但仍把事件建模错误地固定为月度。
- 结论：正式链路以 Tushare 为主，AKShare 只用于交叉校验当前成分或应急降级。

### 决策 2：以“调样事件日历”作为快照抓取的唯一驱动
- 选择：新增 `csi1000_rebalance_calendar` 文件或同等结构化输入，明确记录 `effective_date`、事件类型、来源和版本。
- 原因：中证1000的核心不是“每月成分如何”，而是“哪些事件日会发生成分变动”。日历驱动比固定月度抽样更贴近真实机制，也更易审计。
- 备选：
  - 固定月末抓取：简单，但与半年度定期调整和临时调整都不一致。
  - 运行时直接从远端接口逐日查询：成本高、波动大，不利于复现。
- 结论：先固定日历，再按日历抓取快照。

### 决策 3：导入链继续复用 `snapshots -> changes -> import` 模式
- 选择：保留当前 `CSI800` 已验证过的变更重建模式，给 `CSI1000` 单独实现日历驱动版的 snapshots 和 changes 产物。
- 原因：现有数据库结构已经基于 `start_date/end_date`，无需再改表；复用这一模式可以最小化引擎侧改动。
- 备选：
  - 直接把每个事件快照整张表写入数据库：查询成本和存储重复度更高。
  - 运行时现算 diff：会把数据工程复杂度推到回测主链上。
- 结论：重建 changes 文件，再导入 `pit_index_constituents`。

### 决策 4：扩展现有 membership 质量分类与阻断门禁，而不是重做一套新逻辑
- 选择：复用当前 `membership_audit` / `data_bundle_builder` 已有的质量分类和阻断入口，在其上补入调样日历版本、coverage 缺口和正式 lineage 证据，而不是再新增一套平行审计逻辑。
- 原因：仅靠日志提醒不够；但当前仓库已经有一版初始门禁，重复实现只会制造双口径和不可归因的分叉。
- 备选：
  - 只打印 warning：太弱，无法阻止正式研究误用。
  - 旁路现有门禁，新建 CSI1000 专用校验链：短期能跑，但会和既有 universe audit 产生重复职责。
  - 一律阻断任何低保真运行：会妨碍应急研究和本地排障。
- 结论：默认阻断正式研究；允许显式低保真模式继续，但必须把风险写入元信息和审计证据。

### 决策 5：把质量与 lineage 字段写入 `run_meta.json`
- 选择：在 resolver/data bundle 元信息中增加 `membership_source`、`membership_data_quality`、`distinct_start_dates`、`open_rows`，以及 `rebalance_calendar_version`、`rebalance_calendar_source`、`rebalance_calendar_generated_at` 等字段。
- 原因：这条链最终要服务研究、报表和前端验证，因此质量信息必须和结果产物一起落盘，而不是藏在抓取脚本输出里。
- 备选：
  - 只在导入脚本打印统计：运行后难以追溯。
  - 只写 `audit.json`：太靠后，不利于前端直接展示。
- 结论：`run_meta` 是一等公民，必要时由 `audit.json` 再引用。

### 决策 6：正式 lineage 必须切换到新日历驱动链路
- 选择：更新 `backend/core/universe/lineage.py` 中 `CSI1000` 的导入资产与说明，使其默认指向新的“调样日历 -> snapshots -> changes -> import”链路；旧的静态和月度脚本仅保留为 fallback/排障入口。
- 原因：如果 lineage 仍然指向旧脚本，研究者即使拿到新数据，也无法从文档和产物上判断哪条链路才是正式口径。
- 备选：
  - 保持旧脚本列表不变，只在 README 或 change 文档里口头说明：实现成本低，但容易让正式与应急链路混淆。
- 结论：正式 lineage 与正式数据链必须同步切换。

## Risks / Trade-offs

- [Risk] 中证官方临时调整事件收集不全，导致日历漏项  
  → Mitigation：把调样日历显式版本化，并允许后续补录；只要日历有缺口，数据质量降级为 `approximate`，不得冒充正式 PIT。

- [Risk] Tushare 历史接口在部分年份或事件日可能存在缺口  
  → Mitigation：抓取阶段输出 coverage 统计和缺口清单；缺口未消除前，不允许标记为 `pit_verified`。

- [Risk] 引入运行前阻断后，现有依赖静态 `CSI1000` 的本地实验会被打断  
  → Mitigation：保留显式低保真 override，但强制在元信息中标记风险等级。

- [Risk] 把 `CSI1000` 质量字段写入元信息会增加输出协议复杂度  
  → Mitigation：新增字段集中放在 universe/data bundle 元信息下，避免污染策略绩效字段。

## Migration Plan

1. 新增 `CSI1000` 调样日历文件和抓取脚本，先在离线链路生成 `snapshots` 与 `changes`。
2. 扩展 `import_csi1000_pit.py`，使其记录正式来源标签并输出结构化统计。
3. 扩展现有 `membership_audit` / `data_bundle_builder` 门禁逻辑，把日历版本、coverage 缺口和 lineage 证据一并写入 `run_meta.json`。
4. 扩展 `audit.json` / 报告输出，使 membership 审计失败能被结构化引用，而不是只落在日志里。
5. 更新 `CSI1000` 的正式 lineage 入口和导入资产说明，切换到新链路，默认拒绝静态 fallback 的 `PIT_DYNAMIC` 运行。
6. 保留静态 fallback 作为显式低保真模式，便于排障；如需回滚，只需恢复旧导入数据并关闭审计门禁。

## Open Questions

- 是否需要把中证官方公告原文或公告链接也纳入调样日历，作为审计证据的一部分。
- 正式研究运行的“阻断”应放在抓取/导入阶段，还是放在 `build_data_bundle` 阶段执行；前者更早，后者更贴近运行时。
- 是否同步补 `000852.SH` 的 benchmark 日线入库；这不是本次 change 的核心，但会影响后续 `CSI1000` baseline 研究是否真正可比。
