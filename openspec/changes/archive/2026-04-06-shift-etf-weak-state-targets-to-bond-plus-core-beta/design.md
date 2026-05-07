## Context

当前 ETF 弱势承接已经具备正式合同、seat floor 与非再平衡日 redeploy 入口，但研究结果显示系统在 `RISK_OFF` 下仍偏向“尽量缩到最小”，不符合“个人多资产趋势配置系统”对弱势承接的直觉要求。用户已明确偏好：

- `RISK_OFF` 不要完全空仓
- 承接结构以债为主，允许少量核心宽基
- 黄金先退出弱势正式角色
- 先修仓位行为直觉，不优先追求更高收益

因此本轮应只改 ETF 弱势正式目标映射，不把 execution constraint、stock、regime、combo 结构混进同一轮研究。

## Goals / Non-Goals

**Goals:**
- 将 ETF 弱势正式目标映射切到“债 + 核心宽基”。
- 让 `RISK_OFF` 表现为防守优先但不空仓的累积状态。
- 让 `TRANS_DOWN` 表现为债为主的过渡累积状态。
- 保持本轮改动可归因，便于后续继续研究 execution constraint。

**Non-Goals:**
- 不修改 `stock` 腿。
- 不修改 `regime` 定义。
- 不修改 combo `50/50`。
- 不修改 ETF 弱势总暴露。
- 不在本轮处理 execution constraint 本身。

## Decisions

### Decision 1: `RISK_OFF` 采用债 70 / 核心宽基 30
- 采用 `511010.SH 70% + 510300.SH 30%`。
- 原因：这能把 `RISK_OFF` 从“接近空仓”改成“债为主的低风险累积”，同时给核心 beta 留出明确、可解释的小仓位入口。
- 不采用黄金的原因：当前目标不是做宏观对冲层，而是先把弱势仓位行为收成“债 + 宽基”的直觉型配置。

### Decision 2: `TRANS_DOWN` 采用债 55 / 核心宽基 45
- 采用 `511010.SH 55% + 510300.SH 45%`。
- 原因：`TRANS_DOWN` 应比 `RISK_OFF` 更积极，但仍保持债为主，避免直接退回高 beta 进攻逻辑。
- 不采用更激进比例的原因：这会把本轮研究从“弱势目标结构”扩张成“风险预算提升”。

### Decision 3: 保持总暴露与执行约束不变
- 本轮只改弱势状态下的目标构成，不改 `target_exposure_by_state_5`。
- 原因：如果同时改目标结构和总暴露，回放结果无法归因。
- 不直接改 execution constraint 的原因：上一轮已经把主失败原因收敛到了 execution constraint，本轮先把弱势目标长什么样收清楚，再决定是否值得放松执行约束。

## Risks / Trade-offs

- [风险] 债 + 宽基结构仍可能因为 execution constraint 而没有形成更多实际买单
  → Mitigation：本轮验收同时观察 formal targets、实际非零持仓率和原因码，不只看收益。

- [风险] 去掉黄金可能削弱极端宏观冲击下的对冲表现
  → Mitigation：黄金只是退出本轮弱势正式角色，不影响后续单独研究“债 + 宽基 + 黄金”的替代方案。

- [风险] `TRANS_DOWN` 过于接近 `RISK_OFF`，导致层级分离不明显
  → Mitigation：验收时单独比较两种状态下的实际 ETF 暴露和资产构成，如果重合过高，再起单改动调整。

## Migration Plan

1. 在 ETF formal contract 中新增“bond plus core beta weak-state policy”配置入口与默认值。
2. 将 `RISK_OFF` 与 `TRANS_DOWN` 的正式 target map 切到债 + 核心宽基。
3. 保持现有 total exposure、seat floor、redeploy、execution constraint 逻辑不变。
4. 先用 ETF standalone 回放，再用 `A_STOCK_ETF_V1` 组合复核。
5. 如果结果不符合预期，直接回退 policy 配置与弱势 target map。

## Open Questions

- 当前 `510300.SH` 是否足够作为唯一核心宽基，还是未来要引入第二个核心宽基分桶。
- 在本轮目标结构收口后，是否需要专门起下一轮 change 处理 weak-state execution constraint。
