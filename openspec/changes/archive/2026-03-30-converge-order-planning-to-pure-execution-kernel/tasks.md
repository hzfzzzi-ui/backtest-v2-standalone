## 1. 纯执行入口与上游接线

- [x] 1.1 新增 stage 主路径专用的纯执行级订单构建入口，只接收已确认的计划项、轮换卖出计划和执行级必要参数；DoD：新入口不再暴露 `candidate_plan_mode`、`cash_aware_search_top_n`、`rotation_replace_*`；验证：相关单测；风险：与旧入口下单结果不一致。
- [x] 1.2 调整 `candidate_plan` 适配层，把 stage 主路径需要的已确认计划项稳定挂到运行时日上下文，供 `order_planning` 直接消费；DoD：`order_planning` 无需再自己推导计划项；验证：stage adapter 回归；风险：上游 payload 与内部运行时结构不一致。

## 2. order_planning 边界收敛

- [x] 2.1 精简 `order_planning`，移除候选边界/候选规划回退构建逻辑；DoD：缺少上游正式产物时显式报错；验证：新增单测；风险：暴露既有隐藏接线问题。
- [x] 2.2 让 `order_planning` 改用纯执行入口，不再通过旧入口传入候选规划兼容参数；DoD：stage 主路径只消费 `candidate_plan_v1` 和执行级参数；验证：`test_multi_alpha_order_planning.py` 与相关契约回归；风险：旧的 debug/审计摘要断裂。

## 3. 审计与文档同步

- [x] 3.1 调整正式审计与日终记账，使候选规划层和纯执行层拒绝来源可区分；DoD：正式产物存在三层摘要；验证：审计契约测试；风险：历史诊断口径变化。
- [x] 3.2 同步 `docs/02_系统架构设计/全系统架构设计.md` 中的执行链描述；DoD：文档明确 `order_planning` 为纯执行内核；验证：人工自检；风险：文档晚于实现。

## 4. 回归与基线验证

- [x] 4.1 跑通 `order_planning`、stage adapter、审计相关回归；DoD：受影响 pytest 套件通过；验证：pytest；风险：测试仍耦合旧入口细节。
- [x] 4.2 在容器内重跑 `baseline_V10.1` 并与官方锚点对比；DoD：关键绩效、交易数和预热起点无漂移；验证：容器重跑 + `perf.json`/`run_meta.json` 对账；风险：环境差异导致假阳性漂移。
