## 1. 执行入口与路由收敛

- [x] 1.1 将 runtime service 调用链收敛到 `foundation_shell`，并移除应用层对 strict / legacy 主循环的直接依赖。
- [x] 1.2 将 `strategy -> provider` 映射正式收敛到 `route_registry.py`，避免 strict 主函数继续承担 route 选择职责。

## 2. 执行总线 Contracts 与模块边界

- [x] 2.1 固化 `RuntimePlan`、`ExecutionIntent`、`AccountingSnapshot` 契约，并让 planning / fill / accounting 通过显式 contract 交接核心状态。
- [x] 2.2 将 built-in module 类型限制到 `candidate_filters / rankers / gates / exits / sizers / reporters`。
- [x] 2.3 明确 provider 仅保留 `precompute + day_signals` 职责，并移除 provider 对 `portfolio_builder.py` 的直接依赖。

## 3. 收缩 Strict 与 Legacy

- [x] 3.1 将 [portfolio_simulator_strict.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/portfolio_simulator_strict.py) 压缩为薄 shim，只保留转调和兼容职责。
- [x] 3.2 将 [portfolio_builder.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/portfolio/portfolio_builder.py) 的纯函数继续外提到独立模块，并把旧主循环沉到 `legacy_loop.py`。
- [x] 3.3 冻结 `legacy_adapter.py` 和未来的 `legacy_loop.py`，禁止新逻辑继续进入 legacy 路径。

## 4. Goldens 与审计

- [x] 4.1 建立最小覆盖集 goldens：`baseline_V10`、一个 locked candidate preset、一个 generic route、一个 breakout route。
- [x] 4.2 对每个 golden 固定校验 `orders / trades / NAV / perf / counters`，确保任何一项偏移都能被检测。
- [x] 4.3 对 rolling / rank / zscore、市场状态、财务和行业快照相关迁移执行单独时间可得性审计，并继续以 `baseline_V10_1 -> exp_20260314_144548534_7db9` 作为 10.1 回归锚点。

## 5. 删除路径与文档

- [x] 5.1 按既定顺序准备 legacy 删除：strict 主流程分支 -> `legacy_adapter.py` / `legacy_loop.py` -> 旧 route 特判残留，并把触发条件与删除顺序写入文档。
- [x] 5.2 记录 bus-first 扩展纪律和单轮实验单层归因规则，确保后续 AI / 人工扩展都遵循同一入口。
