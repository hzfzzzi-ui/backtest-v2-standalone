## 1. Overlay 运行时接线

- [x] 1.1 新增 moneyflow overlay loader，支持读取 `monthly_factor_panel.csv` 与 `monthly_coverage_ledger.csv`，并生成按 decision date 冻结的分数映射。DoD：能从配置路径成功加载并返回 `23-26` 日频冻结结果；验证：新增单测覆盖路径解析、月份冻结和 gate 关闭；风险：观察日/执行日错位。
- [x] 1.2 在 breakout provider 与订单规划链路接入 overlay 配置，默认关闭且不影响旧行为。DoD：`asset_context.moneyflow_overlay` 可驱动 `shadow / tiebreak / soft_weight` 分支；验证：新增运行时单测覆盖关闭态与三种模式；风险：误改 baseline 默认排序。

## 2. 诊断与实验定义

- [x] 2.1 补齐 overlay 诊断输出，把启用状态、观察日、gate 状态和候选 overlay 分数写入现有日频/候选诊断。DoD：实验产物中能定位每天 overlay 是否生效及候选分数；验证：新增单测或 golden 检查对应字段存在；风险：诊断字段缺失导致结果不可审计。
- [x] 2.2 新增 `23-26` overlay study 定义，包含 `B0 / TIEBREAK / SOFT_WEIGHT` 变体，并把 overlay 输入路径写死到现有月频 study 产物。DoD：study loader 能成功加载，request payload 含 overlay 配置；验证：study loader 单测或实际 dry-run；风险：路径写错导致实验无法运行。

## 3. 实验执行与核验

- [x] 3.1 运行 `23-26` overlay 实验并保留结果目录、关键指标与对 baseline 的差异摘要。DoD：至少完成 `B0 / TIEBREAK / SOFT_WEIGHT` 三个变体运行；验证：结果目录、`perf.json`、对比摘要存在；风险：实验中途失败或数据路径不可用。
- [x] 3.2 回写 OpenSpec 任务状态并整理验证、风险与回退说明。DoD：任务清单与实际实现一致；验证：`tasks.md` 勾选完成且最终说明可复现；风险：实现与 spec 脱节。
