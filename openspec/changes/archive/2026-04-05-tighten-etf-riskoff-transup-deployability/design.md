## Context

当前 research mainline 使用 `governed_broad_based_standalone_mainline` + `broad_based_standalone_mainline_v1`。这一路径下，contract 仍复用统一的 `deployment_pace` 求解逻辑：

- `TRANS_UP` 退化为 floor-only pace
- `RISK_OFF` 退化为 `0.0`
- provider 在非调仓日只支持 formal `TRANS_UP` 单席 redeploy，不支持 research standalone mainline 的 live 补仓
- non-phase1 provider 对已有持仓默认拒绝再次 BUY，导致即便 deployment pace 为正，也很难把已有仓位补到目标

这使得 study 配置里的正 target 暴露在 runtime 中长期停留在纸面层。

## Goals / Non-Goals

**Goals:**

- 只修改 ETF 单腿 research standalone mainline 在 `RISK_OFF / TRANS_UP` 下的部署合同。
- 让 provider 能在非调仓日执行与合同一致的 `inter_rebalance_deploy`。
- 把 `TRANS_UP` 的实际暴露显著抬升，并尽量把 `BULL` 的平均实际暴露带近目标。
- 保持 formal Phase 1 / strategic beta stabilizer 合同不被本轮 research mainline 改动污染。

**Non-Goals:**

- 不改 ETF 池与 symbol 角色分配。
- 不改 `BULL` 的 target 配置和 BULL 专用 deployment formula。
- 不改 combo、前端、Governor 主合同。
- 不把 research-only 行为伪装成 formal mainline。

## Decisions

### 1. 只对 research standalone mainline 开放新部署语义

决策：
- 仅当 `strategy_role=governed_broad_based_standalone_mainline` 且 `exposure_policy_family=broad_based_standalone_mainline_v1` 时，启用本轮 `RISK_OFF / TRANS_UP` 部署改动。

原因：
- 当前 formal stabilizer 已有独立 contract 与测试边界；本轮目标是修复 research-only 主线，不应顺手改 formal 真相。

备选：
- 直接修改所有 ETF contract 的 `RISK_OFF / TRANS_UP` 公式。
- 放弃，原因是会污染 formal 边界，超出本轮范围。

### 2. `TRANS_UP` 改为 target-backed live deploy，而不是 floor-only

决策：
- 在 standalone mainline 下，`TRANS_UP` 的 `deployment_pace` 直接对齐已批准的 `target_exposure`，并允许 provider 在非调仓日对已选中的 live seat 执行补仓。

原因：
- 当前 `TRANS_UP` 平均目标约 `0.9`，但平均 deployment pace 只有约 `0.446`，而且绝大多数日期停留在 `hold_until_rebalance`。这不是选标失败，而是合同和执行路径共同把 approved target 压成了纸面预算。

备选：
- 仅在状态切换边沿做一次 redeploy。
- 放弃，原因是边沿触发太稀疏，无法稳定把平均实际暴露推近目标。

### 3. `RISK_OFF` 允许 core-only、低速、小额 live accumulation

决策：
- 在 standalone mainline 下，`RISK_OFF` 的 `deployment_pace` 不再固定为 `0.0`，而是至少允许达到 `min_deployable_exposure`，并且只允许对 `core_accumulator` 做非调仓日累积。

原因：
- 用户明确要求在弱市保留小幅 A 股承接；同时这也能减少从 `RISK_OFF` 恢复到 `TRANS_UP/BULL` 时的仓位爬坡成本。

备选：
- `RISK_OFF` 直接允许 full target deploy。
- 放弃，原因是这会把 `RISK_OFF` 变成进攻状态，风险过高。

### 4. provider 必须允许 held symbol top-up

决策：
- 对本轮新增的 `inter_rebalance_deploy` path，provider 允许对已持有 symbol 再次发 BUY，用绝对目标仓位驱动补仓。

原因：
- 当前 non-phase1 path 遇到 held symbol 会直接 return，导致 live 补仓路径天然失效。

备选：
- 只允许 flat-to-long，不允许 top-up。
- 放弃，原因是无法把已有仓位补到合同批准的目标。

### 5. 审计只补最小证据，不扩主 schema

决策：
- 复用现有 `execution_path / pace_policy_gap / rebalance_timing_gap / execution_residual_gap` 结构，只新增清晰的 reason code 与 path 名称。

原因：
- 本轮重点是行为收口，不是再扩一套新审计协议。

## Risks / Trade-offs

- [风险] `TRANS_UP` live deploy 过强，可能抬高回撤
  → 缓解：只开放给 research standalone mainline，并以 `2012-01-01` 到 `2026-03-24` 的审计结果复核。

- [风险] 非调仓日允许 held symbol top-up 可能影响其他 research profile
  → 缓解：仅在新增 deploy path 下显式允许，不改默认 BUY 规则。

- [风险] 只改 `RISK_OFF / TRANS_UP` 后，`BULL` 偏差仍可能大于 `10%`
  → 缓解：本轮先验证是否能通过弱市与恢复期 carry 把 `BULL` 拉近；若仍失败，明确给出“BULL 合同自身仍是硬上限”的证据。

- [风险] 研究路径和 formal 路径发生语义漂移
  → 缓解：formal 路径测试保持原样，新增分支只对 standalone mainline 生效。
