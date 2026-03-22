## Context

当前 `CSI800` 正式入口仍是 [backend/scripts/fetch_csi800_pit.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/fetch_csi800_pit.py)，它会把 `Tushare index_weight` 按月末重建成 snapshots，然后再通过 [backend/scripts/import_csi800_pit.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/import_csi800_pit.py) 与旧 `000906.SH` 历史做 patch merge。这个组合有两个结构性问题：

- 正式 source label 天然带 `monthly`，会被 membership audit 稳定降级为 `approximate`
- patch merge 会保留旧链，容易形成 `mixed` source，导致 `universe_lineage` 无法升回 `PASS`

这次设计的目标不是给 `CSI800` 加新策略，而是把 `HS300_ZZ500` 的正式成分历史链切成单源、非月度、可回放的 `Tushare` 历史链。

## Goals / Non-Goals

**Goals:**
- 为 `000906.SH` 建立一条正式 `Tushare` PIT 历史链，基于实际 `trade_date` 变化而不是月末近似。
- 让正式 refresh 和 lineage 默认指向新链，并把旧月度脚本降为 fallback/兼容路径。
- 让 `import_csi800_pit.py` 支持显式的全量替换导入，避免 `mixed` source。
- 输出结构化摘要，便于后续人工核验历史覆盖、usable dates 和 source label。

**Non-Goals:**
- 不在本次变更中修改任何策略参数、选股逻辑、执行时点或 baseline 口径。
- 不在本次变更中引入新的 benchmark、regime 或前端展示协议。
- 不在本次变更中同时重构 `CSI1000` 数据链；该链保持现状。
- 不承诺本次变更自动补齐远端数据缺口；远端覆盖仍以 `Tushare` 实际返回为准。

## Decisions

### 决策 1：正式 `CSI800` PIT 链使用 `Tushare trade_date` 变化链，而不是继续沿用月度重建
- 选择：新增独立脚本，直接读取 `index_weight(index_code='000906.SH')` 的 `trade_date` 集合，并只保留完整 800 成分的有效日期，再从相邻有效集合变化重建 changes。
- 原因：当前审计真正阻塞的是 `monthly` 和 `mixed`，而不是缺少单独的月末文件。直接使用 `trade_date` 变化链可以在最小改动下去掉近似口径。
- 备选：
  - 继续使用月度脚本并只改 source label：实现最省事，但属于伪修复，不提升真实可信度。
  - 直接做完整 rebalance calendar 方案：证据等级更高，但范围更大，不适合作为这一轮最小正式修复。

### 决策 2：正式导入采用全量替换，旧 patch merge 只作为显式兼容路径保留
- 选择：给 `import_csi800_pit.py` 增加 `--replace-existing`，正式 refresh 默认走全量替换 `000906.SH` 分区。
- 原因：只要继续保留旧历史再 patch merge，就很容易得到 `mixed` source，正式 `PASS` 无法稳定成立。
- 备选：
  - 保持默认 patch merge：兼容性高，但正式链仍有混源风险。
  - 新增单独 importer：边界更清楚，但脚本面会重复膨胀。

### 决策 3：正式 lineage 和 refresh 切换到新脚本，旧脚本降为 fallback 说明
- 选择：更新 `backend/cli/managed/refresh_csi800_pit.py` 和 `backend/core/universe/lineage.py`，正式入口指向新历史脚本；旧 `fetch_csi800_pit.py` 保留但只标注为 approximate/fallback。
- 原因：如果 formal lineage 仍指向旧月度脚本，即使数据库内容正确，系统文档和运行说明仍会继续传播错误口径。
- 备选：
  - 直接就地改写旧 `fetch_csi800_pit.py`：改动更少，但语义切换过于隐蔽，不利于回滚。

### 决策 4：结构化摘要放在脚本输出和 ops summary，而不是额外扩展运行产物协议
- 选择：抓取和导入脚本输出 `summary.json`，包含 usable/skipped trade dates、rows、distinct_start_dates、source 等关键指标。
- 原因：这次是数据链治理，不是 runtime 产物协议变更。先把链路可核验做稳，比扩协议更重要。
- 备选：
  - 直接把更多字段塞进 `run_meta.json`：需要额外跑回测才能看见，不适合导入链自身的健康检查。

## Risks / Trade-offs

- [Risk] `Tushare index_weight` 在部分日期可能返回不完整集合，导致可用 trade_date 稀疏  
  → Mitigation：只接受完整 800 成分日期，并在 summary 中显式输出 skipped/usable 统计；若没有可用日期则直接失败。

- [Risk] 全量替换导入一旦输入文件不完整，会覆盖掉已有较好的 `000906.SH` 历史  
  → Mitigation：正式 refresh 仅在抓取成功且 changes 非空时继续导入，并输出导入前后摘要；保留旧 merge 模式用于手工修补。

- [Risk] 旧脚本仍留在仓库里，后续有人可能继续误用  
  → Mitigation：在 lineage 和 refresh 正式入口中把旧脚本降为 fallback 说明，并通过测试固定正式命令面。

- [Risk] 即使切到正式 `Tushare` 链，远端历史覆盖仍可能有缺口  
  → Mitigation：本次只保证口径正确和单源导入，是否达到 `PASS` 仍以实际 refresh 后的 membership audit 为准。

## Migration Plan

1. 新增 `CSI800` 正式 `Tushare` 历史抓取脚本，并生成 `snapshots.csv`、`changes.csv` 与 `fetch_summary.json`。
2. 扩展 `import_csi800_pit.py` 的 source label、结构化摘要和 `--replace-existing` 导入路径。
3. 更新 `refresh_csi800_pit.py`，让默认正式 refresh 指向新脚本并在 importer 上显式传递 `--replace-existing`。
4. 更新 `backend/core/universe/lineage.py`，把 `HS300_ZZ500` 的正式 import assets 指向新链，旧月度脚本降为 fallback。
5. 补充单元测试，固定抓取、导入和 refresh 的正式命令面。
6. 如需回滚，只需把 refresh/lineage 指回旧月度脚本，并恢复 importer 的 merge 口径。

## Open Questions

- 是否需要在后续单独再开一个 change，把 `CSI800` 升级到显式 rebalance calendar 元数据链，以进一步提高证据等级。
- 正式 refresh 是否要增加一个 `--dry-run` 只输出 summary 不落库；这对运维更友好，但不阻塞本次最小实现。
