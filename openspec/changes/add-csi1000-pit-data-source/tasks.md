## 1. 调样日历

- [x] 1.1 新增 `CSI1000` 调样日历文件与字段约定；DoD：存在可读的 `effective_date/source/event_type/version` 结构；验证：样例文件可被脚本加载；风险：定期调整和临时调整字段语义不一致。
- [x] 1.2 实现调样日历校验；DoD：能检测重复日期、乱序和覆盖缺口；验证：构造异常日历时脚本报错；风险：覆盖范围判断规则过严导致误阻断。

## 2. 抓取与变更重建

- [x] 2.1 新增 `CSI1000` 日历驱动抓取脚本；DoD：按调样日历抓取快照并输出 snapshots 文件与日历元信息；验证：脚本可生成 `snapshots.csv` 且记录来源标签、`calendar_version`；风险：远端数据源个别日期返回缺口。
- [x] 2.2 复用现有 diff 逻辑生成 `csi1000_pit_changes.csv`；DoD：changes 文件包含 `index_code/symbol/in_date/out_date/source`，且可追溯到对应日历版本；验证：相邻快照变更可被正确重建；风险：临时调整与定期调整同日时 diff 归并异常。
- [x] 2.3 扩展 `import_csi1000_pit.py` 输出结构化导入统计；DoD：导入后可看到 `rows/distinct_symbols/distinct_start_dates/open_rows/min_start_date/max_start_date`，并记录 `rebalance_calendar_version/source/generated_at`；验证：导入日志与数据库统计一致；风险：只删 `000852.SH` 分区的约束被破坏。
- [x] 2.4 更新 `backend/core/universe/lineage.py` 中 `CSI1000` 正式导入资产；DoD：正式 lineage 指向新日历驱动链路，旧静态/月度脚本仅作为 fallback 说明；验证：lineage 输出不再把旧脚本当正式入口；风险：排障脚本入口被误删。

## 3. 运行时审计与元信息

- [x] 3.1 扩展现有 runtime membership 质量分类；DoD：在现有 `pit_verified/approximate/static_fallback` 基础上结合来源标签、历史形态和调样日历 coverage 证据判定质量；验证：静态快照样本被识别为 `static_fallback`，日历缺口样本被降级为 `approximate`；风险：分类规则漏判低保真数据。
- [x] 3.2 扩展现有正式研究阻断门禁；DoD：`CSI1000 + PIT_DYNAMIC + static_fallback` 默认被拒绝，且错误信息包含审计指标；验证：受控样本运行时报出可审计错误；风险：误伤排障场景。
- [x] 3.3 将 `membership_source`、`membership_data_quality`、`rebalance_calendar_version`、`rebalance_calendar_source`、`rebalance_calendar_generated_at` 等字段写入 `run_meta.json`；DoD：运行产物能展示 lineage、日历版本与质量；验证：`run_meta.json` 包含新增字段；风险：字段命名与现有产物协议冲突。
- [x] 3.4 将 membership 审计结构化证据写入 `audit.json` 或等价审计产物；DoD：审计失败时可引用 `audit_reason`、coverage 指标和 lineage 字段，而不是仅保留自由文本日志；验证：单次运行产物可被人工定位具体阻断原因；风险：审计输出与现有报告协议冲突。

## 4. 验证与归档

- [ ] 4.1 以正式链路重新导入一版 `CSI1000` 数据并做数据库体检；DoD：`000852.SH` 不再呈现单一 `start_date` 的静态形态；验证：SQL 统计显示存在多个生效日期和移出记录；风险：远端历史覆盖不足。
- [ ] 4.2 运行一次 `CSI1000` universe 解析与回测烟囱验证；DoD：resolver/data bundle/run_meta/audit 产物能稳定输出新质量字段和日历版本字段；验证：单次回测产物通过人工审计；风险：回测链路的旧假设依赖静态 fallback。
- [x] 4.3 记录可复现命令和失败降级策略；DoD：change 内文档明确正式运行命令、低保真 override 和回滚方式；验证：他人可按文档复现；风险：命令与容器环境不一致。
