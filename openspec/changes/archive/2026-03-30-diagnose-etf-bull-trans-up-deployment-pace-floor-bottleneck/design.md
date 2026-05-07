## Context

当前正式 ETF stabilizer 最新实验 [exp_20260329_071754120_c37c](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260329_071754120_c37c) 已经把 `TRANS_UP` 收敛为 `single-seat core recovery`，但 `CAGR` 仍只有 `0.31%`。现有事实显示，主瓶颈已经从 seat 合同矛盾转移到 `deployment_pace` 的 floor 限制：

- `BULL`：平均 `target=0.2`、`floor=0.108`、`overlay=0.072`、`pace=0.108`、`actual=0.1447`，且有 `174` 个 `positive target + zero actual` 交易日。
- `TRANS_UP`：平均 `target=0.1`、`floor=0.0527`、`overlay=0.0`、`pace=0.0527`、`actual=0.0291`，且有 `133` 个 `positive target + zero actual` 交易日。
- `BULL` 的买入全部来自 `monthly_rebalance`；`TRANS_UP` 的买入只有 `10` 笔 `state-change redeploy` 和 `1` 笔 `monthly_rebalance`。

这说明当前系统已经能输出目标和实际，但还不能清晰回答三个问题：

1. 哪些缺口是 contract 层主动保守，哪些只是执行节奏造成。
2. `BULL` 和 `TRANS_UP` 的瓶颈是否同源。
3. 后续如果要改 pace，究竟该改合同、改节奏，还是改执行路径。

## Goals / Non-Goals

**Goals:**

- 为 formal ETF stabilizer 建立 `BULL/TRANS_UP` 专用的 `deployment_pace` 诊断真相链。
- 让日级产物和 research audit 能明确拆出 `approved_target -> floor/overlay -> pace -> execution_path -> actual`。
- 让审计能够把缺口归因为 `pace_policy_gap`、`rebalance_timing_gap` 或 `execution_residual_gap`。
- 为后续独立 L3 提供稳定证据基线，但本次不抢跑到优化实现。

**Non-Goals:**

- 不修改 `deployment_pace` 的计算公式。
- 不修改 Governor 下发预算、slot cap 或 seat 合同。
- 不调整 ETF 池、RS 排序、月频 rebalance 或 `controlled_accumulation`。
- 不把这次研究结果包装成收益优化。

## Decisions

### 1. 以 `approved target -> pace -> actual` 作为唯一诊断主链

选择：

- 诊断主链统一使用正式产物里已有的 `etf_target_exposure`、`etf_strategic_floor_target`、`etf_tactical_overlay_target`、`etf_deployment_pace`、`etf_actual_exposure`。
- 不再引入第二套研究侧重算 target，也不从 `orders.csv` 反推新的 target 真相。

原因：

- 这样可以保持“配置唯一真相”和“产物唯一真相”。
- 这次要研究的是为什么 pace 只到 floor，不是再引入一套新的解释器。

备选但不采用：

- 从订单层反推“真实节奏 target”作为诊断真相。  
  否决，因为那会把执行结果倒灌成合同真相，审计会再次漂移。

### 2. 把缺口拆成三类 owner，而不是继续用笼统的低部署描述

选择：

- `pace_policy_gap`：`approved target` 与 `deployment_pace` 的差值，代表合同主动保守。
- `rebalance_timing_gap`：`deployment_pace > 0` 但执行路径是 `hold_until_rebalance` 或等价月频等待，代表节奏滞后。
- `execution_residual_gap`：在 `pace` 已允许、且非纯节奏等待后仍未落成实际仓位的残差，代表 lot/cash/持仓继承等执行层影响。

原因：

- 只有这样，后续才知道该开“改 pace”还是“改节奏”的 L3。
- 当前 `BULL` 和 `TRANS_UP` 的问题结构已经不一样，不能再混成一个数字。

备选但不采用：

- 只输出 `target - actual` 总缺口。  
  否决，因为这无法区分是 policy、timing 还是 execution。

### 3. `BULL` 和 `TRANS_UP` 必须独立结论，不能混表

选择：

- 日级汇总、研究审计和诊断摘要都必须分别输出 `BULL` 与 `TRANS_UP` 的均值、计数、gap attribution。

原因：

- `BULL` 仍保留 overlay；`TRANS_UP` 已收敛成 `single-seat core recovery`。两者如果混表，会把 seat 合同差异误写成 pace 问题。

备选但不采用：

- 继续只输出统一的 ETF underdeployment 指标。  
  否决，因为这正是当前研究无法收敛的原因。

### 4. 这次 change 只做诊断合同，不做行为修复

选择：

- 本次只要求实现最小可观测字段、归因逻辑和实验对照摘要。
- 不改变正式 ETF 策略行为。

原因：

- 这是标准 L3 研究前置步骤，先固化证据链，再决定优化方向。

备选但不采用：

- 顺手把 `BULL/TRANS_UP` 的 `pace` 一起放大。  
  否决，因为那会把“诊断”和“优化”绑在一次实验里，结果无法归因。

## Risks / Trade-offs

- [风险] 诊断字段扩张后，用户可能误把 `pace_policy_gap` 当成 bug。  
  缓解：在 spec 和 audit 中明确这只是 owner attribution，不自动等价为缺陷。

- [风险] `execution_residual_gap` 容易把已有持仓继承与真实漏部署混在一起。  
  缓解：要求 audit 同时引用 `execution_path` 和 reason code，不允许只看净差值。

- [风险] 本次不改行为，可能被误解成“没有推进收益优化”。  
  缓解：在 proposal 和最终结论里明确这次目标是为下一条 pace 优化 L3 提供稳定基线。

## Migration Plan

1. 扩展 ETF 正式日级字段与订单元数据，加入 `pace` 缺口分解字段。
2. 扩展 `research_audit`，输出 `BULL/TRANS_UP` 独立的 gap attribution。
3. 补齐 contract/provider/accounting/audit/schema 单测。
4. 重跑正式 ETF 子实验，生成新的 bottleneck 摘要，作为后续 pace 优化锚点。
5. 如需回退，只回退新增诊断字段和审计归因逻辑，不触碰策略行为。

## Open Questions

- `rebalance_timing_gap` 是否只在 `execution_path=hold_until_rebalance` 时成立，还是也要覆盖 `await_monthly_rebalance` 等兼容 reason code。
- `execution_residual_gap` 是否需要按 `core/satellite/defense` 再细拆，还是先保留实验级一层归因即可。
