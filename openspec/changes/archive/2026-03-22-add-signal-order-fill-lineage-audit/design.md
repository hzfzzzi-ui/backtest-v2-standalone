## Context

当前正式主线的 execution audit 以天级摘要为主，能够看到 `days_with_fills`、`days_with_scheduled_orders`、成交结果和少量 execution realism 样本，但看不到单条信号如何演化成订单并最终成交。`timing_alignment` 目前主要依赖 `compiled_plan.json`、`input_config.json` 和 stage metadata 推断 next-day contract，缺少显式的 `signal -> order -> fill` 证据链。

这让两个问题长期悬空：

- 无法正式证明某条成交是否确实源于前一交易日信号，而不是同日成交或链路漂移
- 无法在正式审计中区分 dropped order、missing fill、cancel/reject、schedule drift 等不同失败类型

这次 change 需要横跨信号生成、订单规划、fill accounting、artifact finalize 和 golden 合同，因此先收敛设计。

## Goals / Non-Goals

**Goals:**
- 为正式执行链引入稳定、可复现的 `signal_id`、`order_id`、`fill_id` 及父子关系。
- 新增单级生命周期台账产物，记录 `generated -> scheduled -> submitted -> filled/rejected/canceled/expired` 等关键状态流转。
- 让 `audit.json` 只保留 lineage 摘要、异常样本和明细引用，不把全量台账直接塞进主审计文件。
- 让 `timing_alignment` 在存在显式 lineage 证据时优先消费该证据，而不是仅靠配置推断。

**Non-Goals:**
- 不改变策略信号逻辑、订单排序逻辑或撮合逻辑。
- 不把 blocked signal 全量并入订单生命周期台账；阻断原因仍由既有 diagnostics/funnel 表达。
- 不在本 change 中引入外部券商、OMS 或真实执行系统集成。
- 不做盘口级或逐笔撮合审计，仍以当前日线执行抽象为边界。

## Decisions

### 决策 1：lineage id 必须在执行链边界生成并向下游传播

采用方案：
- `signal_id` 在正式信号进入执行链时生成
- `order_id` 在订单规划 / 排程阶段生成，并显式指向父 `signal_id`
- `fill_id` 在成交落账阶段生成，并显式指向父 `order_id`
- 所有 id 使用确定性生成规则，保证同一输入下可复现

原因：
- 只有在 ownership 边界生成 id，才能避免事后模糊匹配
- 确定性 id 更符合实验可复现与 golden 校验要求

备选方案：
- 事后用 `symbol/date/side` 模糊回连
  - 放弃原因：同股多信号、多订单、部分成交场景下不可靠
- 使用随机 UUID
  - 放弃原因：破坏复现与 golden 对比

### 决策 2：生命周期台账与 audit.json 分层存储

采用方案：
- 新增单独的 lineage ledger artifact，承载全量生命周期明细
- `audit.json` 只承载摘要计数、异常样本和 ledger 引用

原因：
- 可以控制主审计文件体积
- 允许以后扩展生命周期细节而不污染主 surface

备选方案：
- 直接把全量台账内联进 `audit.json`
  - 放弃原因：产物体积和接口复杂度都会快速失控

### 决策 3：timing_alignment 优先使用显式 lineage 证据，缺失时兼容当前推断逻辑

采用方案：
- 若实验提供 lineage ledger，`timing_alignment` 优先使用显式 `signal_date / scheduled_date / fill_date / terminal_status`
- 若实验尚未提供 lineage 证据，则保留当前基于配置与 stage metadata 的保守推断路径

原因：
- 新旧实验可以平滑兼容
- 不会因为 change 落地初期缺少历史 artifact 而让所有旧实验失效

备选方案：
- 一步切到“无 lineage 即失败”
  - 放弃原因：迁移成本过高，且不利于现有产物兼容

### 决策 4：台账只覆盖执行链事实，不吞并所有 diagnostics

采用方案：
- lineage ledger 只记录正式执行链中已经进入生命周期的实体和状态流转
- blocked signal、risk gate 和 selection funnel 仍留在现有 diagnostics 体系中

原因：
- 这样边界清楚，不会把订单台账变成另一个全能诊断文件

备选方案：
- 把 blocked signal 也纳入同一台账
  - 放弃原因：会把生命周期台账和筛选漏斗耦合，难以维护

## Risks / Trade-offs

- [风险] 执行链多个阶段都要补字段，合同改动面广 → 先定义最小稳定 id 集和最小状态集，分阶段接入
- [风险] 台账体积增长影响产物加载 → 明细与摘要分层，主 surface 只暴露引用和摘要
- [风险] 不同路由的状态流转不完全一致 → 先定义跨路由最小公共状态，特殊状态通过扩展字段表达
- [风险] 历史实验没有 lineage 证据 → `timing_alignment` 保留兼容回退路径，缺证据时降级而非误判

## Migration Plan

1. 定义稳定 lineage id 合同和最小生命周期状态集合。
2. 在正式执行链中逐步接入 `signal_id -> order_id -> fill_id` 传播。
3. 输出独立 lineage ledger artifact，并在 `audit.json` / manifest 中写入摘要和引用。
4. 更新 `timing_alignment` 对显式 lineage 证据的消费逻辑。
5. 补 golden、contract 和 integration 测试，覆盖代表性路由。

回退方案：
- 若主链接入不稳定，可先停止写出 lineage summary 和 gate 消费，同时保留旧的 timing 推断路径。
- 由于台账独立落盘，回退时只需撤回新 artifact 和引用字段，不影响现有 perf/nav/audit 主结构。

## Open Questions

- 是否需要把 `submitted` 与 `scheduled` 区分为两个正式状态，还是在当前日线回测抽象下合并即可。
- 对“已排单但无成交且无显式取消”的情况，是统一记为 `expired` 还是保留更细的未终结状态。
