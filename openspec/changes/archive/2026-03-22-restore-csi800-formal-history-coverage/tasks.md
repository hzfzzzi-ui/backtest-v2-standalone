## 1. 变更固化

- [x] 1.1 补齐 `restore-csi800-formal-history-coverage` 的 proposal/design/specs，明确“seed 长历史 + tail patch + 覆盖校验”正式链；DoD：change artifacts 可用于 apply；验证：`openspec status --change restore-csi800-formal-history-coverage --json` 显示 apply-ready；风险：把恢复操作和数据治理边界写混。

## 2. 正式链实现

- [x] 2.1 新增 `backend/scripts/build_csi800_formal_history.py`，支持从 seed CSV 与可选 patch CSV 物化单一 `csi800_formal_history` 链；DoD：能输出 formal `changes.csv` 与 `summary.json`；验证：新增 unit test 覆盖 seed-only 与 seed+patch；风险：patch 边界截断错误。
- [x] 2.2 扩展 `backend/cli/managed/refresh_csi800_pit.py`，加入 `--seed-csv`、覆盖校验和 materialize 步骤；DoD：无 seed 且覆盖不足时命令失败，有 seed 时走 `fetch -> materialize -> import`；验证：refresh 单测覆盖两条分支；风险：运维命令面变化导致旧脚本误用。
- [x] 2.3 更新 `backend/core/universe/lineage.py` 与相关测试，formal lineage 改为正式历史链物化入口；DoD：`HS300_ZZ500` notes/import assets 与真实运行链一致；验证：lineage 单测通过；风险：文档和实际入口再度漂移。

## 3. Docker 恢复与复审

- [x] 3.1 在 Docker 内用现有 `000906.SH` 长历史备份和当前 `Tushare` patch 物化 formal chain，并对数据库执行全量替换；DoD：`pit_index_constituents(index_code='000906.SH')` 恢复 `2007+` 覆盖且 source 单一；验证：ops summary 记录恢复前后对比；风险：误用错误 seed 文件。
- [x] 3.2 重跑 `baseline_V10.1` 并复审 `universe_lineage`；DoD：给出明确的 PASS/WARN/FAIL 结论和对应 exp_id；验证：读取新实验的 `audit.json`、`run_meta.json`、`perf.json`；风险：即使恢复长历史，仍可能因其他数据漂移未回到 PASS。
