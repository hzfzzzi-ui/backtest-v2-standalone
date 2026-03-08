## Context

当前公开主链已经稳定为：

`config_json -> compiler -> DataBundle -> foundation shell -> stage pipeline shell -> legacy adapter -> legacy execution kernel`

上一轮 `v2-legacy-accounting-boundary-shrink` 已经把开盘成交、日度 NAV 快照和结果桥接从
`legacy_adapter.py` 中拆出。现在这个文件剩余的核心责任主要是：

- stage 是否可用的 route/applicability 判定
- route-specific 的 `effective_max_positions / dd_state / market_state / trade_mode / benchmark_regime_on / risk_on_today`
- provider day signal 的 route-specific 后处理
- route/day-control 相关的诊断计数更新

这些逻辑仍然集中在 adapter runtime 内部，导致两个问题：

1. route-specific orchestration 还没有和 runtime 容器真正分离。
2. 后续如果要替换掉 legacy route 细节，仍然必须直接修改单体 adapter。

## Goals / Non-Goals

**Goals:**

- 把 `legacy_adapter.py` 剩余的 route/day-control/provider diagnostics 责任拆到专用内部模块。
- 保持公开单路径、T+1 时序、交易数学和实验产物口径不变。
- 让 `legacy_adapter.py` 进一步收敛为 runtime 容器和薄编排边界。
- 继续以 `exp_20260308_021045840_cde0` 为锁定基线验证结果等价。

**Non-Goals:**

- 不改写 execution kernel。
- 不改变 `portfolio_builder.py` 中的下单、成本或 metrics 数学。
- 不改前端配置协议或公开 API。
- 不在本 change 中删除 provider 或 route 旧实现。

## Decisions

### D1. 按 route orchestration 责任拆分为 3 个内部模块

本 change 只拆三类模块：

- `stage_applicability.py`
  - 负责 `disabled_stages` 与 `stage_is_applicable(...)`
- `day_controls.py`
  - 负责 `_compute_day_controls(...)` 和相关 route/day-control 诊断计数
- `signal_postprocess.py`
  - 负责 provider day signal 的 route-specific 后处理

这样每类都对应清晰边界，不需要在这一步重写 runtime 结构。

备选方案：把 route-specific 逻辑合并进 `route_runtime.py`。  
未采用原因：`route_runtime.py` 当前更偏静态初始化与 precompute，日内 controls/postprocess 属于动态路径，混在一起会重新放大模块职责。

### D2. 保持 `LegacyStageAdapterRuntime` 作为状态容器

抽出的 helper 继续读取 runtime 上既有字段，或最小化接收必要参数；不在这一轮引入新的 route context class。

这样可以保证：

- day control 更新顺序不变
- market filter / benchmark regime / provider 风险状态读取顺序不变
- diagnostics 计数更新点不变

备选方案：为 route/day-control 单独引入 immutable context。  
未采用原因：收益有限，但会同时改变多个调用面。

### D3. `ensure_day(...)` 和 `_provider_precompute(...)` 仍留在 adapter 中

本轮不动：

- `_provider_precompute(...)`
- `ensure_day(...)` 主时序

但它们内部调用的 route/day-control/postprocess 逻辑应迁到 helper。

备选方案：继续把 `ensure_day(...)` 彻底打散。  
未采用原因：那会和上一轮 accounting 变更叠加，归因会变差。

### D4. 所有 route-control 抽分步骤继续服从锁定基线门禁

每个任务组都必须通过：

- 聚焦单测
- `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`

允许的非阻塞漂移仍然只限于已接受的 `report.html` diagnostic hash drift。

## Risks / Trade-offs

- [Risk] route control 抽分后计数更新顺序变化，导致 `run_meta` 或 metrics 漂移  
  → Mitigation：保留原有调用时点，只迁移实现体，不改变主时序。

- [Risk] provider postprocess 拆分后 buy signal 过滤条件顺序变化  
  → Mitigation：先补 route-specific 聚焦测试，再做 helper 抽分。

- [Risk] `stage_is_applicable(...)` 独立后和 stage shell 的 disabled stage 语义不一致  
  → Mitigation：把 disabled stage、route applicability、neutral output 路径一起纳入单测。

## Migration Plan

1. 先抽 `stage_applicability.py`，把 stage 可用性判定迁出 `legacy_adapter.py`。
2. 再抽 `day_controls.py`，迁出 `_compute_day_controls(...)` 和相关计数更新。
3. 再抽 `signal_postprocess.py`，迁出 provider day signal 的 route-specific 后处理。
4. 补 route/day-control/postprocess 聚焦测试。
5. 运行锁定基线复跑，确认核心产物继续 `PASS`。
6. 更新冻结文档，明确 `legacy_adapter.py` 剩余允许持有的责任。

## Open Questions

- route/day-control 迁出后，`_provider_precompute(...)` 是否应在下一条 change 中与 route initialization 一起并入更清晰的 route shell。
- `stage_is_applicable(...)` 后续是否应与 stage pipeline shell 的 enabled stage summary 共用一份标准化摘要结构。
