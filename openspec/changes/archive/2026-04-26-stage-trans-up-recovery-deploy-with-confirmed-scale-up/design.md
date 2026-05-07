## Context

当前已经验证：

- `allow_trans_up_recovery_entries_when_benchmark_off` 对 `2018-2022` 与 `2023-2026` 是正向的。
- 同一开关放到 `2012-2026` 全路径后，`2012-2017` 的 `TRANS_UP` 被明显打坏。
- 根因不是恢复态没有候选，而是恢复态放开后仓位直接抬到接近常态，坏仓大量拖入 `BEAR / RISK_OFF_EXIT`。

当前执行链里，`candidate_plan` 已消费 `signal.meta.order_value_scale`。因此最小实现不需要改执行内核，只需要在恢复态放行路径上给买入信号打缩放即可。

## Goals / Non-Goals

**Goals:**
- 为 `TRANS_UP + benchmark_regime_off` 提供单独的恢复态轻仓缩放配置。
- 保持默认值 `1.0`，避免未显式开启时污染主线。
- 增加诊断字段，明确当天是否走了 staged deploy 以及实际应用的缩放值。
- 用最小 A/B 验证它是否能缓和 `2012-2017` 的恢复态损伤。

**Non-Goals:**
- 不实现恢复态持仓上的主动 pyramiding。
- 不修改股票池、ETF 腿、账户层预算或其它状态的部署逻辑。
- 不引入第二套恢复态打分体系。

## Decisions

### 决策 1：用 `order_value_scale` 做恢复态轻仓，而不是改 max positions 或执行内核
- 方案：新增 `trans_up_recovery_entry_scale_when_benchmark_off`，仅在 `TRANS_UP + benchmark_off + recovery gate relaxed` 时乘到买入信号的 `meta.order_value_scale` 上。
- 原因：
  - 现有 `candidate_plan` 已消费该字段。
  - 这是最小改动，不需要改 shared execution 或 order sizing 内核。
- 备选方案：
  - 改 `effective_max_positions`：会同时改变候选规划与库存路径，归因更脏。
  - 改执行内核下单金额：会把研究逻辑下沉到执行层，不合当前边界。

### 决策 2：确认后加仓采用“回到原有正常部署路径”，不做显式加仓器
- 方案：缩放只在 `benchmark_regime_off` 时生效；一旦恢复到原有风险门控条件，后续新开仓自动回到未缩放路径。
- 原因：
  - 最小实现可直接回答“先轻仓是否足够缓和前段损伤”。
  - 显式 pyramiding 会引入第二个高风险变量。
- 备选方案：
  - 在 `benchmark_regime_on` 后对已有持仓强制加仓。当前阶段不做，因为会引入持仓级副作用。

### 决策 3：默认值保持 `1.0`
- 方案：新字段默认 `1.0`，不改变当前行为。
- 原因：
  - 当前 change 的目标是研究，不是未经验证就改主线。

## Risks / Trade-offs

- [风险] 缩放过低会重新压死恢复态参与。 → 缓解：最小 A/B 先用单一值 `0.3`，只比较与 `1.0` 的差异。
- [风险] 缩放只能控制“先轻仓”，不能解决“确认后主动加仓”。 → 缓解：本次明确只验证第一段，不把 pyramiding 混入同一实验。
- [风险] 诊断字段增加后，如果前端或报表误读为正式主字段，可能制造新口径。 → 缓解：只写入现有 diagnostics/meta，不新增主输出 schema。
