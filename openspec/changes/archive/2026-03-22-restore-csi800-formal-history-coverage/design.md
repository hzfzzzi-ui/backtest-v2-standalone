## Context

当前正式 `CSI800` refresh 路径已经改为 `fetch_csi800_pit_history.py -> import_csi800_pit.py --replace-existing`，但容器内实测 `Tushare index_weight(index_code='000906.SH')` 无论请求 `2007-01-01` 到 `2026-03-31` 还是更早区间，都只返回 `2025-07-31` 到 `2026-02-27` 的 8 个 `trade_date`，其中只有 7 个日期是完整 800 成分集合。直接全量替换会把 `000906.SH` 的长历史从 `2007-01-01` 缩短到 `2025-08-29`，使 `baseline_V10.1` 的 universe 口径断裂。

仓库里已经存在一次正式前备份 `outputs/ops/csi800_pre_refresh_backup_20260312_024254/pit_index_constituents_000906_backup.csv`，其 source 单一为 `jqdatasdk_pit_snapshot`，覆盖 `2007-01-01` 到 `2026-02-01`。本次设计的目标是在不回退审计口径的前提下，把这个长历史恢复成正式可导入链，并让后续 refresh 不再误覆写数据库。

## Goals / Non-Goals

**Goals:**
- 建立一条 `CSI800` 正式历史链物化步骤，能够把长历史 seed 与可用的 `Tushare` 尾部变更整合为单一 formal chain。
- 让正式 refresh 在没有长历史覆盖时阻断导入，并在提供 seed 时生成覆盖 `2007+` 的正式链再做全量替换。
- 恢复 Docker 中 `000906.SH` 的长历史，重审 `baseline_V10.1`，确认 `universe_lineage` 是否回到 `PASS`。

**Non-Goals:**
- 本次不改变任何策略参数、执行时点、选股逻辑或 baseline 配置。
- 本次不试图证明 `Tushare` 已具备独立的 `2007+` 全历史覆盖；如果远端没有，系统只做保护和物化，不伪造原始来源。
- 本次不扩展 `pit_index_constituents` 表结构；provenance 通过 ops summary 和 formal source label 管理。

## Decisions

### 决策 1：新增正式历史链物化脚本，输入是长历史 seed 和可选 `Tushare` patch，输出是单一 formal chain

- 选择：新增 `backend/scripts/build_csi800_formal_history.py`，读取 seed CSV 和可选 patch CSV，沿用现有 patch 截断语义生成最终 `changes.csv`，并把所有行统一标记为 `csi800_formal_history`。
- 原因：直接把 seed 备份重新导入虽然能恢复 baseline，但后续一旦叠加 `Tushare` patch 就会再次落回 `mixed` source；把正式运行链抽象成“formal history materialization”后，runtime 消费的是单一正式链，而 provenance 保留在 summary。
- 备选：
  - 直接恢复 `jqdatasdk_pit_snapshot` 原 label：短期最省事，但后续无法无缝接入 `Tushare` 尾部更新。
  - 让数据库长期保留 mixed raw rows：无法稳定通过 `universe_lineage`。

### 决策 2：正式 refresh 必须做覆盖校验，不能再无条件 `--replace-existing`

- 选择：`refresh_csi800_pit.py` 在 import 前读取 fetch/materialize summary。若无 seed 且抓取结果不能覆盖 `required_start`，命令直接失败并跳过导入；若提供 seed，则改为 `fetch -> materialize -> import`。
- 原因：这次事故的核心不是抓取失败，而是把“不足以全量替换”的结果当成了正式全量链。
- 备选：
  - 仅靠人工先看 summary 再决定是否导入：容易再次误操作。
  - 自动 merge 回数据库旧历史：会把正式链和库内当前状态耦合，回退不清晰。

### 决策 3：formal lineage 文案改为“seed/正式链物化”而不是“裸 Tushare 历史抓取”

- 选择：`HS300_ZZ500` 的 formal import assets 改为包含 `build_csi800_formal_history.py`，notes 明确说明 `Tushare trade_date` 只是 formal chain 的 tail update 来源。
- 原因：运行时真正可信的对象是物化后的正式链，而不是远端原始返回本身。
- 备选：
  - 保持现有文案不变：会继续误导运维以为裸 `Tushare` 抓取可直接全量替换。

## Risks / Trade-offs

- [Risk] `csi800_formal_history` 是经过物化的正式链，不再等同于单一原始供应商标签。  
  -> Mitigation：在 materialize summary 中显式输出 `seed_source`、`patch_source`、覆盖范围和 patch 边界，保留可审计 provenance。
- [Risk] seed 文件路径若依赖某一次 ops 备份，运维可移植性会变差。  
  -> Mitigation：refresh 只支持显式 `--seed-csv`，不硬编码时间戳路径；本次 Docker 恢复用现有备份手工指定。
- [Risk] patch 合并边界处理错误会截断 seed 历史或重复尾部记录。  
  -> Mitigation：复用现有 `_merge_rows` 语义，并补 unit test 覆盖 seed+patch 合并场景。
- [Risk] 即使恢复到 `PASS`，未来若继续直接用裸 `Tushare` refresh 仍可能再次破坏长历史。  
  -> Mitigation：通过 refresh 覆盖校验把这种误用直接变成失败。

## Migration Plan

1. 新增正式历史链物化脚本和对应测试。
2. 扩展 `refresh_csi800_pit.py` 的覆盖校验与 `--seed-csv` 路径；更新 lineage 文案。
3. 在 Docker 中用已有长历史备份 + 当前 `Tushare` patch 生成 formal chain，并对 `000906.SH` 执行全量替换。
4. 重跑 `baseline_V10.1`，确认 `universe_lineage` 与 perf 是否恢复。
5. 如需回退，直接用恢复前的 `000906.SH` 备份 CSV 重新执行一次 `import_csi800_pit.py --replace-existing`。

## Open Questions

- 这条 formal chain 后续是否需要沉淀为长期受管的 seed 文件，而不是只依赖 ops 备份。
- 当 `Tushare` 将来提供更长历史时，是否要再开单独 change，把 seed 从人工备份替换为新的正式供应链。
