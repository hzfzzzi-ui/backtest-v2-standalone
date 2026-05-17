## 1. Baseline 证据核对

- [x] 1.1 核对旧锚点、新候选、ETF 组件实验、首个分歧日和分红现金事件证据。DoD：形成可引用的迁移事实；验证：读取 `perf.json`、`portfolio_cash_events.csv`、`run_meta.json`；风险：误把收益差异解释为策略优化。
- [x] 1.2 核对当前 `outputs/baselines` 注册结构和 active baseline 来源。DoD：明确需要更新的最小文件集合；验证：读取 baseline index 和 baseline record；风险：误改展示层文件或重复 active baseline。

## 2. Baseline 重锚

- [x] 2.1 将新候选 `exp_20260508_124555553_fabd` 注册为当前 active stock+ETF baseline。DoD：baseline truth 指向新候选实验；验证：baseline record 的 `linked_exp_id` 可解析；风险：compare truth 仍指向旧实验。
- [x] 2.2 将旧锚点 `exp_20260426_005716047_8650` 显式降级为 replay/audit anchor。DoD：旧锚点不再作为 live baseline；验证：active baseline 唯一；风险：丢失回滚证据。
- [x] 2.3 写入迁移说明，记录 ETF 分红事件行数、首个分歧日、分歧标的和核心指标变化。DoD：人工审计能解释本次漂移；验证：迁移说明存在并引用对应实验；风险：未来无法区分数据口径变更与策略变更。
- [x] 2.4 将 baseline regression 的 `portfolio_trades.csv` 比较改为忽略 `component_exp_id` 的语义 hash。DoD：运行期组件实验 ID 不再造成假失败；验证：单元测试覆盖；风险：组件来源变化需继续由 `run_meta` 和执行合同约束。

## 3. 回归验证

- [x] 3.1 在 Docker 容器内重跑 baseline regression。DoD：命令完成并产生日志；验证：exit code 和 stdout/stderr 日志；风险：Docker/数据库状态导致假失败。
- [x] 3.2 确认新 baseline 对自身回归通过。DoD：baseline regression 返回 `PASS`；验证：`baseline_compare_status` 或 compare 输出；风险：注册文件与 regression truth 未对齐。
- [x] 3.3 若回归失败，保留失败日志并停止，不接受重锚完成。DoD：失败原因可追踪；验证：本次最终回归为 `PASS`，无需触发失败处理；风险：在失败状态下误报完成。
