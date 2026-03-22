## 1. 研究合同与配置入口

- [x] 1.1 固化该研究的 OpenSpec artifact 与研究定义骨架；DoD：`proposal/design/spec/tasks` 完整、`research/studies` 下新增十年窗口 study 定义骨架并声明独立研究身份；验证：`openspec status --change add-a-share-moneyflow-divergence-factor-study --json` 显示 design/specs/tasks 就绪，study YAML 可被 loader 解析；风险：只写文档不写研究定义会导致“已定义但不可调用”。
- [x] 1.2 为十年窗口补齐运行参数合同；DoD：研究定义显式包含 `2016-2026` 窗口、独立输出目录、`partial_coverage`/`data_unreliable` 所需元字段；验证：study payload 经 `backend/research/study_definition.py` 校验通过；风险：沿用现有 baseline append 约定会把独立研究误并入主线。

## 2. 数据读取与日期门控

- [x] 2.1 在数据提供层新增 `moneyflow` side-table 读取接口；DoD：运行时可按 `symbol + trade_date` 读取 `net_mf_amount` 与覆盖率判定所需字段，不改主表合同；验证：新增 provider 单测覆盖字段映射、日期过滤和空结果行为；风险：side table 与主表日期未严格对齐会引入时间错位。
- [x] 2.2 接入观察日白名单或等价覆盖率输入；DoD：运行时能对每个月末观察日给出 `tradable` / `skipped_low_coverage` / `blocked_missing_gate` 判定；验证：用已有审计样本构造测试，检查 95%/90% 门槛与缺白名单阻塞行为；风险：把近似覆盖率误当成正式白名单会削弱审计强度。

## 3. 月频因子与组合执行

- [x] 3.1 实现单日与月度主力分歧率面板；DoD：系统能按 `abs(net_mf_amount) / avg20(circ_mv)` 生成单日值，并按月聚合为月度均值，严格执行 20 日完整窗口和月内有效日下限；验证：新增单测覆盖窗口边界、缺失处理和最小有效日规则；风险：任何 `NULL -> 0` 或窗口 off-by-one 都会直接污染最小值排序。
- [x] 3.2 实现月末观察、次月首开调仓的研究执行链路；DoD：系统能在每月月末选出最小 10 只股票，在次月首个交易日开盘按目标组合再平衡；验证：新增研究级回放测试，检查观察日与执行日错位、保留持仓与替换持仓行为；风险：错误复用日频策略会把月频研究偷换成日频择时。

## 4. 产物、可靠性标记与十年运行

- [x] 4.1 补齐月份级诊断产物；DoD：运行产物至少包含 `monthly_coverage_ledger.csv`、`monthly_factor_panel.csv`、`monthly_selection.csv`、`monthly_universe_stats.csv`，并在摘要中输出 `planned_rebalance_months`、`tradable_months`、`skipped_months`、`partial_coverage`；验证：本地十年 smoke run 后产物齐全且字段可读；风险：缺少月份 ledger 会导致跳过月份无法审计。
- [x] 4.2 实现 `data_unreliable` 可靠性判定与 baseline 隔离；DoD：当 `tradable_months / planned_rebalance_months < 0.85` 时运行被标记为 `data_unreliable`，且不会默认追加到 baseline 报告；验证：构造低覆盖月份样本测试摘要标记和报告分流；风险：若仍默认 baseline append，会把探索性结果误包装成正式结论。
- [ ] 4.3 启动 `2016-2026` 十年回测并沉淀最小运行说明；DoD：在上述能力全部接通后完成一次真实十年运行，生成标准产物与月份级诊断，并记录复现命令；验证：人工抽查月末月份、低覆盖跳过和交易日志一致性；风险：当前能力未接通前强行开跑，只会产出伪结果而不是有效研究。

## 5. 递减权重扩展

- [x] 5.1 在研究 spec / design 中固定 `weight_mode` 合同；DoD：明确默认 `equal_weight` 与新增 `rank_decay_linear` 的定义、边界和“不改变选股集合”约束；验证：OpenSpec artifact 更新完成；风险：若不先固化权重模式定义，后续回测将不可复现。
- [x] 5.2 在月频回放执行器中实现按 rank 线性递减权重构建目标仓位；DoD：`weight_mode = rank_decay_linear` 时按 `N + 1 - rank` 归一化分配目标价值，旧等权结果保持不变；验证：新增单测覆盖权重归一化、单调性和选股集合不变；风险：若把权重模式混入选股阶段，会污染因子研究口径。
- [x] 5.3 新增 `Top5` 与 `Top10` 的递减权重 variants 并跑通 `2326_HC`；DoD：生成独立产物并完成和现有 `Top5/Top10` 等权版本的横向对比；验证：真实 study_run 成功并输出 perf/nav/selection；风险：若只改代码不跑真实窗口，无法判断递减权重是否真能在不扩容的前提下改善质量。
