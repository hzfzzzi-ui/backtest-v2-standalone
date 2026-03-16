## Context

当前仓库已经完成 runtime、API surface、study 入口和结果面重构，剩余主要问题不再是 legacy 兼容壳，而是 5 个热点文件继续承担过多职责：

- `strict_runtime_default.py`：单函数同时处理输入归一化、benchmark 数组、信号矩阵、逐日循环和结果汇总。
- `regime_router_signal_provider.py`：单类同时承载 façade、strategy 参数抽取、precompute、route dispatch 和诊断计数。
- `breakout_signal_provider.py`：虽然已拆出部分 helper，但 `__init__` 仍是巨大状态容器，provider 仍混着参数、状态和 route 行为。
- `runner_config_helpers.py`：单文件同时承担 workbench -> runtime config 编译、locked candidate 入口和 semantic bundle 组装。
- `artifacts_impl.py`：单文件同时承担 artifact I/O、manifest 生成、漏斗与诊断汇总、结果稳定化。

本轮 change 的关键约束是：允许内部结构激进清理，但禁止改动 `baseline_V10.1 -> exp_20260314_144548534_7db9` 的研究口径和执行结果。

## Goals / Non-Goals

**Goals:**

- 将 5 个热点文件拆成清晰的 façade + 专用模块结构。
- 让 runtime/provider/API compile/artifact finalize 的职责边界可以被独立维护和测试。
- 在不改 public contract 的前提下，把后续新资产扩展点从单文件热点中释放出来。
- 将验证路径锁定为 `baseline_V10.1` 前后对照，确保拆分是机械性的而不是行为性的。

**Non-Goals:**

- 不在本轮改变任何策略参数默认值、执行时点、成交规则或指标口径。
- 不在本轮重写 `strict_runtime_default.py`、`regime_router_signal_provider.py` 或 `breakout_signal_provider.py` 的核心算法。
- 不在本轮扩展新的资产类型、study 能力或前端功能。
- 不追求把 façade 文件彻底删到零；本轮允许它们保留稳定入口职责。

## Decisions

### 决策 1：按职责边界拆，不按行数拆

选择：

- `strict_runtime_default.py` 按 `input / benchmark / signal / daily-loop / result` 五个阶段拆。
- provider 文件按 `config / state / precompute / day-routes / façade` 拆。
- `runner_config_helpers.py` 按 `universe / signal / risk-exit / bundle` 拆。
- `artifacts_impl.py` 按 `io / manifest / stage-summary / diagnostics / finalize` 拆。

原因：

- 按行数切块只会把混乱复制到更多文件，不能形成后续可维护边界。
- 按职责拆，才能把后续“新增一个配置域”“新增一种 diagnostics”“新增一个 provider route”落到正确模块。

备选方案：

- 继续只抽若干 helper。
  - 放弃原因：过去几轮已经证明只抽 helper 不足以解决 state 和 façade 混杂问题。

### 决策 2：public façade 先保留，内部实现先迁出

选择：

- 保留原 5 个热点文件作为稳定 façade/入口。
- 先迁出内部逻辑，再让 façade 只做调度。

原因：

- 可以最小化外部 import 和测试改动范围。
- 便于以 `V10.1` 对照验证“仅结构变、行为不变”。

备选方案：

- 直接改 public import 路径。
  - 放弃原因：会把“结构拆分”叠加成“调用方迁移”，扩大风险面。

### 决策 3：provider 先收 state，再拆 route

选择：

- 对 `regime_router_signal_provider.py` 和 `breakout_signal_provider.py`，先把参数快照与运行时 ndarray/state 收进 dataclass 或集中 state 对象，再拆 `precompute/day route`。

原因：

- provider 当前最大问题不是函数多，而是 `self` 上散落几十个状态字段。
- 如果不先收 state，拆到多个文件后仍然会依赖分散字段，复杂度不会下降。

备选方案：

- 先把 `day_signals` 再拆成更多 helper。
  - 放弃原因：只会制造更多跨文件隐式状态依赖。

### 决策 4：`strict_runtime_default.py` 只做阶段性机械拆分

选择：

- 默认 route 只允许做阶段模块外提和 façade 编排收口。
- 拆分顺序固定：输入 -> benchmark -> signal -> daily-loop -> result。

原因：

- 这是最接近 `V10.1` 执行口径的高风险位置。
- 机械拆分比“顺手优化流程”更可审计，也更容易回滚。

备选方案：

- 借拆分机会顺手统一更多 runtime 行为。
  - 放弃原因：不符合当前“只锚定 V10.1、禁止口径漂移”的约束。

## Risks / Trade-offs

- [风险] façade 与新模块同时存在，短期内文件数量上升  
  → Mitigation：在 spec 和任务里强制 façade 只保留调度，不允许再回流业务逻辑。

- [风险] provider/state 拆分时漏迁某个隐式字段，导致 `day_signals` 行为漂移  
  → Mitigation：先集中 state，再逐块迁移，并对 `V10.1` 做前后指标对照。

- [风险] `runner_config_helpers.py` 和 `artifacts_impl.py` 拆分后 import 图更复杂  
  → Mitigation：新模块一律单向依赖 façade 或 shared primitives，不允许横向互相调用。

- [风险] `strict_runtime_default.py` 拆分过快会误伤默认 route  
  → Mitigation：把它排在最后实现，并要求每个阶段拆分后立即跑回归。

## Migration Plan

1. 先拆 `runner_config_helpers.py`，验证 runtime config 产出不变。
2. 再拆 `artifacts_impl.py`，验证 manifest/surface/standard artifacts 不变。
3. 再拆 `regime_router_signal_provider.py`，先收 state，再迁 `precompute/day routes`。
4. 再拆 `breakout_signal_provider.py`，先收 config/state，再迁 route 逻辑。
5. 最后拆 `strict_runtime_default.py`，按五个阶段外提。
6. 每一阶段都以前后对照 `baseline_V10.1 -> exp_20260314_144548534_7db9` 为门。
7. 任一阶段出现结果漂移，立即回滚该阶段拆分，不继续向下推进。

## Open Questions

- `strict_runtime_default.py` 的阶段模块最终是否保留为单文件 stage helpers，还是继续下沉到 `engine_runtime/` 子目录？本轮先不强制。
- provider state 最终采用 dataclass 还是轻量对象容器？本轮允许按文件特征选择，但必须收口成单一 state owner。
