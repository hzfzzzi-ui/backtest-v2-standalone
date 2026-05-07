## 1. 合同与上游边界接线

- [x] 1.1 在共享阶段流水线合同中新增 `candidate_boundary_v1` 数据结构与最小 payload 规范，并在 `bridge_adapter.ensure_day()` 中接入上游候选边界层；DoD：`current_day` 和阶段输出可稳定访问候选边界 payload；验证：合同单测与 `openspec validate`；风险：新增 payload 与现有 `day_signals`/`target_book` 重复真相。
- [x] 1.2 新增候选边界适配器，把子系统权重解析、市场状态权重覆写、子系统名额分配和候选截断从 `order_planning` 中迁出；DoD：`order_planning` 不再直接持有上述实现；验证：相关单测与 debug payload 对账；风险：迁移过程中 baseline 候选集合偏移。

## 2. 执行内核边界收敛

- [x] 2.1 精简 `order_planning`，让其只消费候选边界层确认后的买入候选和执行级 sizing 参数；DoD：`order_planning` 不再读取 `signal_composition`、`market_state_weight_overrides` 或子系统名额配置；验证：`test_multi_alpha_order_planning.py` 与正式执行合同回归；风险：老 debug 字段断裂。
- [x] 2.2 保持执行级 sizing 行为不变，并补齐 `candidate_plan_mode` 与轮换替换在新边界下的回归；DoD：现金感知搜索、轮换替换、统一目标持仓单继续通过；验证：相关 pytest 套件与 baseline 重跑；风险：误把执行级 sizing 也迁出执行内核。

## 3. 审计与文档同步

- [x] 3.1 调整正式审计与研究诊断，使候选边界拒绝和执行级拒绝分层归因；DoD：`candidate_rows`、日级诊断和研究审计能区分候选边界层与执行内核；验证：审计合同测试与产物对账；风险：历史诊断脚本口径变化。
- [x] 3.2 同步 `docs/02_系统架构设计/全系统架构设计.md` 与 `docs/01_系统接口模块定义/共享层/A股子系统接口模块定义.md` 的正式边界描述；DoD：文档与代码现实一致；验证：人工自检；风险：文档滞后于实现。

## 4. 回归与漂移验证

- [x] 4.1 跑通候选边界、执行内核、研究审计相关单元回归；DoD：受影响 pytest 套件全部通过；验证：pytest；风险：测试仍依赖旧阶段字段。
- [x] 4.2 在容器内重跑 `baseline_V10.1` 并与正式锚点对比；DoD：关键绩效、交易数、起始日期字段无漂移；验证：容器重跑 + `perf.json` 对账；风险：环境差异导致假阳性漂移。
