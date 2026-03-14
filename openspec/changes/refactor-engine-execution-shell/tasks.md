## 1. 执行入口与路由注册

- [ ] 1.1 将 runtime service 调用链收敛到 `foundation_shell`，并移除对 strict/legacy 主循环的直接依赖；DoD: 应用层只调 `foundation_shell`；验证: 运行链路集成测试通过；风险: 入口收敛时遗漏 route 特判。
- [ ] 1.2 将 `strategy -> provider` 映射正式收敛到 `route_registry.py`；DoD: strict 主函数不再承担 route 选择职责；验证: generic/breakout 代表 route 运行正确；风险: route 迁移时隐藏状态丢失。

## 2. 执行总线 contracts 与模块边界

- [ ] 2.1 固化 `RuntimePlan`、`ExecutionIntent`、`AccountingSnapshot` 契约；DoD: planning/fill/accounting 通过显式 contract 交接核心状态；验证: 单元测试覆盖 contract 字段和缺失保护；风险: 隐式字段漏迁导致行为漂移。
- [ ] 2.2 将 built-in module 类型限制到 `candidate_filters / rankers / gates / exits / sizers / reporters`；DoD: registry/resolver 只支持首批模块类型；验证: 模块装配测试通过；风险: 过度抽象再次扩散。
- [ ] 2.3 明确 provider 仅保留 `precompute + day_signals` 职责；DoD: provider 不再直接改现金/仓位/NAV；验证: provider 协议测试通过；风险: 旧逻辑拆分时打穿 10.1 口径。

## 3. 收缩 strict 与 legacy

- [ ] 3.1 将 [portfolio_simulator_strict.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/portfolio_simulator_strict.py) 压缩为薄 shim；DoD: strict 只做转调和兼容；验证: strict 入口仍能回放同一结果；风险: shim 中残留新逻辑入口。
- [ ] 3.2 将 [portfolio_builder.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/portfolio/portfolio_builder.py) 的纯函数外提到 `price_index.py`、`nav_snapshot.py`、`metrics.py`、`selection_order.py`，并将旧主循环沉到 `legacy_loop.py`；DoD: 原文件职责收缩；验证: 相关单元测试与回放通过；风险: 纯函数拆分顺带改口径。
- [ ] 3.3 冻结 `legacy_adapter.py` 和 `legacy_loop.py`，禁止新逻辑进入；DoD: 文档与代码边界一致；验证: 新任务不再引用 legacy 作为扩展点；风险: 迁移期间仍有人继续往里塞逻辑。

## 4. Goldens 与审计

- [ ] 4.1 建立最小覆盖集 goldens：`baseline_V10`、一个 locked candidate preset、一个 generic route、一个 breakout route；DoD: 样本可重复回放；验证: golden 产物固定可对比；风险: 样本代表性不足。
- [ ] 4.2 对每个 golden 固定校验 `orders / trades / NAV / perf / counters`；DoD: 任一项偏移都能被检测；验证: 回归测试红绿明确；风险: 只验 perf 导致细节漂移漏网。
- [ ] 4.3 对 rolling/rank/zscore、市场状态、财务和行业快照相关迁移执行单独时间可得性审计；DoD: 10.1 价格型信号口径无偏移；验证: 审计报告与敏感模块测试通过；风险: 审计覆盖不全。

## 5. 删除路径与文档

- [ ] 5.1 按既定顺序准备 legacy 删除：strict 主流程分支 -> `legacy_adapter.py` / `legacy_loop.py` -> 旧 route 特判残留；DoD: 删除顺序和触发条件写入文档；验证: OpenSpec/README/审计说明同步；风险: 先删后补造成回放中断。
- [ ] 5.2 记录 bus-first 扩展纪律和单轮实验单层归因规则；DoD: 后续 AI/人工扩展都能遵循同一入口；验证: 文档审阅通过；风险: 设计约束未被后续 change 继承。
