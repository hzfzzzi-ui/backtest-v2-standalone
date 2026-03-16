## 1. 历史 Manifest 回填

- [x] 1.1 实现历史实验 `manifest.json` canonical 回填工具，只补 `asset_scope`、`asset_profile_id`、`market_profile_id`、`execution_profile_id` 和 `asset_context` 缺失字段；DoD：工具可对单实验与批量实验运行并输出审计 JSON；验证：迁移 dry-run/real-run 输出；风险：错误推导旧实验资产上下文。
- [x] 1.2 对当前历史实验目录执行回填并生成审计结果；DoD：至少覆盖 `exp_20260314_144548534_7db9` 和其他可见历史实验，跳过项有明确原因；验证：抽查回填后的 `manifest.json` 与审计报告；风险：批量写入范围过大。

## 2. Baseline Gate Contract 更新

- [x] 2.1 更新 `backend/scripts/ops/v2_backend_refactor_baseline_contract.json`，将默认锚点切到 `exp_20260314_144548534_7db9`，并把已批准的资产边界 schema 升级写入 contract 规则；DoD：contract 默认基线与当前正式主线一致；验证：读取 contract 文件并运行 compare；风险：误放宽本应阻塞的漂移。
- [x] 2.2 调整 `baseline_regression_check.py` 的 gate 逻辑，把 `portfolio_daily` 从整文件哈希门收口为稳定语义门，并将 approved schema enrichment 与行为漂移分离；DoD：`perf/nav/trades/candidates/manifest` 仍是阻塞门，新增资产字段不再误报失败；验证：单测与 compare 输出；风险：daily 语义摘要选得过宽。

## 3. 验证与对照

- [x] 3.1 补测试覆盖历史 manifest 回填和 baseline gate 新 contract；DoD：新增/更新单测覆盖回填、approved drift、daily 语义门；验证：`pytest` 指定集合通过；风险：测试只覆盖 happy path。
- [x] 3.2 运行 `baseline_V10.1 -> exp_20260314_144548534_7db9` 对照并输出新的 compare 结果；DoD：生成新的 ops 报告，明确说明 PASS/WARN/FAIL 及剩余差异；验证：`outputs/ops/*compare*.json`；风险：对照报告未反映真实阻塞项。
