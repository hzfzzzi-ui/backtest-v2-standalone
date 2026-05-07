## 1. 候选规划合同与接线

- [x] 1.1 在共享阶段流水线合同中新增 `candidate_plan_v1` 数据结构与最小 payload 规范，并在 `bridge_adapter.ensure_day()` 或等价上游接线点挂入候选规划层；DoD：阶段输出可稳定访问 `candidate_plan_v1`；验证：合同单测与 `openspec validate`；风险：与 `candidate_boundary_v1`、`target_book_v1` 形成重复真相。
- [x] 1.2 新增候选规划适配器，把现金感知搜索、轮换替换和候选规划摘要从 `order_planning` 前移；DoD：候选规划结果在进入执行内核前完成；验证：相关单测与 debug payload 对账；风险：候选集合或替换顺序漂移。

## 2. 执行内核边界收敛

- [x] 2.1 精简 `order_planning`，让其只消费 `candidate_plan_v1`、执行级 sizing 必需参数和 `target_book_v1`；DoD：`order_planning` 不再直接读取 `candidate_plan_mode`、`cash_aware_search_top_n`、`rotation_replace_*`；验证：`test_multi_alpha_order_planning.py` 与正式执行合同回归；风险：老 debug 字段断裂。
- [x] 2.2 保持现有正式 sizing 与成交行为不变，并补齐个股子系统在新边界下的轮换替换回归；DoD：现金/整手/目标持仓行为与现有主线一致；验证：相关 pytest 套件与差异对账；风险：误把执行级 sizing 一并迁出执行内核。

## 3. 审计与文档同步

- [x] 3.1 调整正式审计与研究诊断，使候选边界层、候选规划层和执行内核层的拒绝分层归因；DoD：`candidate_rows`、日级诊断和研究审计能区分三层来源；验证：审计合同测试与产物对账；风险：历史诊断脚本口径变化。
- [x] 3.2 同步 `docs/02_系统架构设计/全系统架构设计.md` 中的阶段流水线描述；DoD：文档明确写出候选规划层位置；验证：人工自检；风险：文档滞后于实现。

## 4. 回归与基线验证

- [x] 4.1 跑通候选规划层、执行内核和审计相关单元回归；DoD：受影响 pytest 套件全部通过；验证：pytest；风险：测试仍依赖旧的候选规划配置字段。
- [x] 4.2 在容器内重跑 `baseline_V10.1` 并与正式锚点对比；DoD：关键绩效、交易数和预热起点字段无漂移；验证：容器重跑 + `perf.json`/`run_meta.json` 对账；风险：环境差异导致假阳性漂移。
