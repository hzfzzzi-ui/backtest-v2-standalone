## Context

当前正式 ETF stabilizer 的实际问题不是“没有目标预算”，而是“恢复期预算没有及时落地”。按最新正式 ETF 子实验，`TRANS_UP` 状态平均 `target_exposure=0.1`、`deployment_pace=0.0527`，但实际平均暴露接近 `0`。主因是 provider 仍然按月频等待 `MONTHLY_REBALANCE`，没有在状态切换到 `TRANS_UP` 时做任何 core floor 的提前承接。

同时，这条线已经是 formal stabilizer 主线，不能为了提 `CAGR` 直接把它改成激进的加仓器。本次设计必须保持：
- Governor 预算为唯一真相
- next-open 执行不变
- monthly rebalance 主语义不变
- non-monthly 日不得偷偷升级成 full rebalance

## Goals / Non-Goals

**Goals:**
- 在 formal ETF stabilizer 中增加 `TRANS_UP` 状态切换触发的单次 floor redeploy。
- redeploy 只允许补齐 `core_accumulator`，不轮换 satellite。
- 保留现有 `deployment_pace` 和 monthly rebalance 主合同，不混入更大的 pace 语义改动。
- 产物中明确写出 redeploy 是否触发、为什么触发、是否因 hard block 或 floor 已满足而未触发。

**Non-Goals:**
- 不改变 `BULL/LIGHT/TRANS_DOWN/RISK_OFF` 的主 rebalance 频率定义。
- 不在本次引入 `controlled_accumulation_mode != none`。
- 不改变 ETF 池、bucket 模板或 RS 参数。
- 不把 `TRANS_UP` redeploy 扩展成 satellite overlay 加仓。

## Decisions

### 1. redeploy 只在 `TRANS_UP` 的“状态切换沿”触发

系统只在状态从 `{LIGHT, TRANS_DOWN, RISK_OFF}` 进入 `TRANS_UP` 时尝试触发 redeploy，而不是每个 `TRANS_UP` 交易日都补仓。

原因：
- 这能直接修复“恢复期第一时间不承接”的问题。
- 也能避免连续多日重复补单，破坏 stabilizer 的低频边界。

备选方案：
- 每个 `TRANS_UP` 日都允许补到 floor。否决，因为会把节奏改得过大。
- 继续只等月末。否决，因为这正是当前瓶颈。

### 2. redeploy 只补 `core_accumulator` 到 strategic floor

系统仅在当前 `actual_core_exposure` 明显低于 `strategic_floor_target` 时，允许生成 core-only 买单；`tactical_satellite` 仍然只由月末 rebalance 决定。

原因：
- 这保持了 stabilizer 的防守属性。
- 也让本次结果归因清楚：修的是恢复期底仓承接，不是进攻性 overlay。

备选方案：
- 同时补 satellite overlay。否决，因为这已经是第二层策略改动。

### 3. redeploy 仍服从 existing execution contract

redeploy 继续遵守：
- Governor hard block
- next-open execution
- lot/cash/sizing 约束
- existing order planning

原因：
- 不能为了提 `CAGR` 引入新的 timing 或记账风险。

### 4. 增加最小审计证据，不扩展到新 audit gate

本次只要求在 ETF 运行产物中新增最小证据：
- state-change redeploy 是否触发
- 触发原因或拒绝原因
- core floor gap 是否存在
- reason_code 区分 monthly selection 与 trans-up redeploy

原因：
- 这次是行为修复，不需要引入新的 research audit gate。
- 但必须保证前后可对账。

## Risks / Trade-offs

- [风险] redeploy 触发过频，意外提高换手。  
  - 缓解：只允许 `TRANS_UP` 状态切换沿触发一次，不是每天触发。

- [风险] core-only redeploy 仍可能因为 cash/lot 约束打折，结果改善有限。  
  - 缓解：本次先把“节奏错过”修掉；如果改善仍有限，再单独研究 sizing 漏损。

- [风险] 非月末下单可能让“为什么今天买了”不再显然。  
  - 缓解：必须增加明确 reason_code 和日级字段，指明这是 `TRANS_UP` state-change redeploy。

- [风险] 如果 `TRANS_UP` 信号抖动，会引入额外 churn。  
  - 缓解：仅在状态切换沿触发，并保留 Governor / state persistence 现有约束。
