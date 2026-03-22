## 1. 正式抓取链

- [x] 1.1 新增 `backend/scripts/fetch_csi800_pit_history.py`，按 `Tushare index_weight.trade_date` 的完整 800 成分集合重建 snapshots 和 changes；DoD：能输出正式 `changes.csv` 与 `summary.json`；验证：新增抓取脚本单测；风险：远端 partial trade_date 会导致可用日期稀疏。
- [x] 1.2 保留旧 `fetch_csi800_pit.py` 作为 fallback，不改变其近似语义；DoD：旧脚本仍可独立运行且不再被正式 refresh 使用；验证：现有旧脚本单测继续通过；风险：脚本边界不清会再次混淆正式与近似链。

## 2. 导入与正式入口

- [x] 2.1 扩展 `backend/scripts/import_csi800_pit.py`，支持 `--replace-existing`、`--summary-out` 和正式 source label 区分；DoD：正式导入可以只替换 `000906.SH` 且输出结构化摘要；验证：新增 importer 单测；风险：误覆盖旧历史。
- [x] 2.2 更新 `backend/cli/managed/refresh_csi800_pit.py` 默认调用新历史脚本，并在正式导入时显式传递 `--replace-existing`；DoD：refresh 命令面稳定指向正式链；验证：refresh 单测更新通过；风险：命令面变更影响已有运维脚本。
- [x] 2.3 更新 `backend/core/universe/lineage.py`，让 `HS300_ZZ500` 的 formal import assets 指向新历史链，旧月度脚本降为 fallback 说明；DoD：formal lineage 文案不再引用月度脚本为正式入口；验证：lineage 相关断言或现有契约测试通过；风险：文档和真实入口不一致。

## 3. 验证

- [x] 3.1 补充并更新 `tests/unit/test_fetch_csi800_pit.py`、`tests/unit/test_import_csi800_pit.py`、`tests/unit/test_refresh_csi800_pit.py`；DoD：覆盖完整 trade_date、全量替换导入和正式 refresh 命令面；验证：目标 pytest 集合全绿；风险：测试只覆盖 happy path。
- [x] 3.2 运行最小验证并记录可复现命令；DoD：能够说明正式抓取、正式导入和回退路径的执行命令；验证：本地 pytest 和必要的编译检查通过；风险：未实际连库时仍需后续人工刷新数据库。
