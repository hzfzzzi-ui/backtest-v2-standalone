## Context

当前正式 ETF stabilizer 的最新诊断实验 [exp_20260329_080608247_fd57](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260329_080608247_fd57) 已经证明，ETF `CAGR` 的主瓶颈不在执行残差，而在 `BULL` 状态下过于保守的 `deployment_pace` 合同。

当前事实：
- `BULL`：平均 `target_exposure=0.2`、`strategic_floor_target=0.108`、`tactical_overlay_target=0.072`、`deployment_pace=0.108`、`avg_pace_policy_gap=0.092`
- `TRANS_UP`：已经收敛为 `single-seat core recovery`，平均 `tactical_overlay_target=0.0`
- `BULL` 和 `TRANS_UP` 的瓶颈结构已经不同，不能再用同一条 pace 调整同时处理

当前约束：
- 不改 Governor 预算合同
- 不改 slot/seat 合同
- 不改 ETF 池、RS 排序和月频 rebalance
- 不重新引入 `TRANS_UP` second-seat overlay

因此，这次应只做最小的 `BULL` pace 合同优化，并保持 `TRANS_UP` 完全不动。

## Goals / Non-Goals

**Goals:**

- 让正式 ETF stabilizer 在 `BULL` 状态下，允许一部分 approved overlay 进入 `deployment_pace`
- 明确收敛 v1 合同参数，避免“部分 overlay”变成不可审计的隐式行为
- 保持 `TRANS_UP` 的 `single-seat core recovery` 不变
- 让日级产物和 research audit 能直接对照变更前后 `BULL` 的 `pace_policy_gap / actual_exposure` 变化

**Non-Goals:**

- 不修改 `TRANS_UP` 的 pace 公式
- 不修改 `TRANS_UP` 的 seat/slot 语义
- 不调整 Governor exposure denominator
- 不调整 rebalance 频率
- 不扩 ETF 池，不修改 RS 逻辑

## Decisions

### 1. 只对 `BULL` 引入 partial overlay pace

选择：
- `BULL` 状态下，`deployment_pace = strategic_floor_cap + bull_partial_overlay_pace_ratio * tactical_overlay_cap`
- `TRANS_UP`、`LIGHT`、`TRANS_DOWN`、`RISK_OFF` 的 pace 公式保持不变

原因：
- `BULL` 当前仍保留 live overlay target，且 `effective_max_positions=2`
- `TRANS_UP` 已正式收敛为 `single-seat core recovery`，继续动它会重新碰 seat 合同
- 先把 `BULL` 单独拉出来，可以最小化归因

备选但不采用：
- 同时调整 `BULL/TRANS_UP`
  - 否决，因为会把 pace 优化和 seat 语义重新绑在一起

### 2. v1 固定采用 `0.5` 的 partial overlay ratio

选择：
- 正式 v1 使用固定 `bull_partial_overlay_pace_ratio = 0.5`
- 它必须进入合同快照和审计证据，不能只留在代码常量里

原因：
- 需要一个可审计、可复现、可回退的最小步长
- `0.5` 足够让 `BULL` 的 pace 显著高于 floor，但不会一步吃满 overlay
- 如果直接放到 `1.0`，这已经更接近 full target deploy，不符合 v1 的保守目的

备选但不采用：
- 直接用 `1.0`
  - 否决，因为改动过大，和“最小可归因 L3”不符
- 让 ratio 完全配置化且默认不固定
  - 否决，因为 v1 先需要清晰、可比较的固定基线

### 3. 保持 monthly rebalance 主节奏不变

选择：
- 月频主 rebalance 不变
- 本次只改变 `BULL` 的“可立即部署预算”，不改“多快触发 rebalance”

原因：
- 当前证据显示 `pace_policy_gap` 大于 `rebalance_timing_gap`
- 先改合同更容易证明收益变化是否来自 `pace`

备选但不采用：
- 同时把 `BULL` 改成更高频 rebalance
  - 否决，因为这样无法区分“更多预算”与“更快节奏”的贡献

### 4. 审计必须显式对照变更前后 `BULL` 的 pace 改善

选择：
- 保留现有 `pace_policy_gap / rebalance_timing_gap / execution_residual_gap`
- 增加 `bull_partial_overlay_pace_ratio` 和 `bull_pace_mode`
- 正式实验摘要必须对照 `BULL` 的 `target / floor / overlay / pace / actual / gap owner`

原因：
- 这次不是只做合同微调，而是要为下一轮 ETF `CAGR` 提升建立基线
- 如果没有对照摘要，很容易把 `BULL` 的收益变化误读成别的原因

备选但不采用：
- 只看 `perf.json`
  - 否决，因为 ETF 当前收益变化很可能较小，单看绩效无法证明合同命中点

## Risks / Trade-offs

- [风险] `BULL` pace 提高后，`actual_exposure` 上升，回撤也可能同步抬高。
  - 缓解：只放开 `0.5 * overlay`，不吃满 overlay；正式实验必须同时汇报 `CAGR` 与 `MaxDD`

- [风险] 如果 `BULL` 下大量日子仍被月频节奏压住，`pace` 放松后收益改善可能不明显。
  - 缓解：保留三段 gap 诊断，明确区分是 `pace_policy_gap` 缩小了但 `rebalance_timing_gap` 仍主导，还是合同本身无效

- [风险] 如果 `BULL` 的实际仓位主要由既有持仓继承贡献，partial overlay 可能提升有限。
  - 缓解：要求审计输出 `BULL` 变更前后 `avg_actual_exposure` 与买单 execution path 对照

- [风险] 将 ratio 固定成 `0.5` 可能不是最终最优值。
  - 缓解：本次目标不是找最优值，而是建立一个可归因的 v1 基线

## Migration Plan

1. 在 ETF contract 中新增 `bull_partial_overlay_pace_ratio`，默认固定为 `0.5`
2. 修改 `BULL` 下的 `deployment_pace` 计算公式；其余状态保持不变
3. 将新 ratio 和 `bull_pace_mode` 贯通到 provider 元数据、`portfolio_daily.csv` 和 `audit.json`
4. 补齐 contract/provider/accounting/audit/schema 单测
5. 重跑正式 ETF study，对照变更前后 `BULL` 的 pace 与绩效
6. 如需回退，只回退 `BULL` partial overlay pace 相关字段与公式，不触碰其他状态

## Open Questions

- `bull_partial_overlay_pace_ratio` 是否仅作为 v1 固定常量，还是下一轮研究再升级为显式配置参数
- 若 `pace_policy_gap` 显著下降但 `CAGR` 提升仍有限，下一条 L3 应优先改 `BULL` 节奏还是 Governor denominator
