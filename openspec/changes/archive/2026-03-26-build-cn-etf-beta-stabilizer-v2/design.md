## Context

当前 `cn_etf_beta` 已具备独立 provider、Governor 接入、research audit 与前端结果入口，但从最近完成的 ETF 规则族研究可以确认：收益差的主因不是“ETF 不可研究”，而是 **ETF sleeve 的实际部署语义仍停留在研究型小仓轮动**。

已知事实：
- 当前最好 ETF 版本仍接近持平，不能独立承担收益目标。
- ETF 全窗口平均实际仓位仅约 `5%`，即使在有持仓的那些天，平均仓位也只有约 `15%`。
- 当前研究候选里，`510300 / 510050` 明显优于 `510500 / 512100`。
- `cash fallback` 与单标的部署让 ETF 更像“战术小仓”，而不是“稳定 beta 层”。

约束：
- 不能破坏 canonical 5-state 与 Governor 总控边界。
- 不能把 ETF beta sleeve 偷偷做成防守层或独立大类资产层。
- 不能在没有证据链的情况下仅凭收益变化判断成功。

## Goals / Non-Goals

**Goals:**
- 把 `cn_etf_beta` 的部署语义调整为更符合 beta 稳定器角色的 V2。
- 让 ETF sleeve 在 `RISK_ON / NEUTRAL` 下具备更合理的部署强度，而不是长期接近不部署。
- 把 ETF sleeve 的 fallback 从“默认现金退出”收敛成可审计、可配置、不会混淆防守层边界的正式口径。
- 让 ETF sleeve 的研究验收不仅看收益，还要看：
  - 实际暴露
  - fallback 使用情况
  - under-deploy 原因
  - Governor 预算约束是否过强

**Non-Goals:**
- 本 change 不实现 unified runtime 的个股+ETF 单实验入口。
- 本 change 不把 `511010` 正式升级成独立防守 sleeve。
- 本 change 不扩 ETF 主候选池，不重新引入 `510500 / 512100 / 512890` 作为正式 V2 主研究池。
- 本 change 不涉及前端布局重构。

## Decisions

### 1. ETF V2 主候选池收敛到 `510300 + 510050`
- 决策：V2 稳定器方案只以 `510300.SH` 和 `510050.SH` 为 core beta 候选。
- 原因：现有研究已经证明这两只更符合当前系统壳；继续把 `510500 / 512100` 放进主研究线只会混入中小盘噪音。
- 备选：
  - 保留四只 core：更“完整”，但会继续模糊问题来源。

### 2. ETF V2 默认允许小规模并持，而不是单 ETF 轮动
- 决策：把 `max_selected_symbols` 的 V2 默认从 `1` 提升到 `2`。
- 原因：beta 稳定器不应继续表现为单标的战术切换，小规模并持更符合稳定 beta 暴露。
- 备选：
  - 继续单 ETF：实现更简单，但仍会保留“轻仓战术轮动”的行为特征。

### 3. fallback 默认从纯现金收敛为正式防守 fallback
- 决策：V2 研究默认用 `511010.SH` 作为正式 fallback，对照组保留 `cash fallback`。
- 原因：如果 ETF sleeve 作为稳定器，风险资产不过滤时直接回现金会过度杀伤长期暴露；但也不能把 fallback 静默写成防守层，需要显式审计。
- 备选：
  - 继续现金 fallback：回撤更好看，但部署过低的问题很难解决。
  - 直接升级成防守层：会混淆 ETF beta 与 future defense sleeve 的边界。

### 4. Governor 需要为 ETF 稳定器提供单独的部署语义
- 决策：Governor 对 ETF sleeve 的 V2 预算不再只继承当前过紧的 deployability 语义，而要显式输出：
  - `target_exposure`
  - `min_deployable_exposure`
  - `fallback_allowed`
  - `under_deploy_reason_codes`
- 原因：当前 ETF 收益差的关键事实是仓位太低，必须把“为什么没上仓”从黑箱变成一等公民。
- 备选：
  - 只在 provider 内放宽：实现快，但会绕开总控，破坏系统解释性。

### 5. V2 验收先看部署改进，再看收益
- 决策：V2 的第一轮验收优先看：
  - 全窗口平均实际仓位
  - 有持仓日平均仓位
  - fallback 使用率
  - under-deploy 原因分布
  - MaxDD / Sharpe 是否恶化
- 原因：当前主问题是部署不足，不先解决这个，收益对比没有解释力。
- 备选：
  - 继续只看 CAGR：会把“仓位太低”的结构问题掩盖掉。

## Risks / Trade-offs

- [ETF 部署抬升后回撤上升] → 用 `Governor + fallback + 审计证据` 同时观察，不允许只看收益。
- [511010 fallback 与未来 defense sleeve 语义重叠] → 明确它在本轮只作为 ETF sleeve-local fallback，不升级成独立正式防守层。
- [并持 2 只 ETF 仍然改善有限] → 允许研究结论是“部署更合理了，但收益仍不值得推进”，不强行升级。
- [Governor 预算语义改动过大影响现有 A 股个股主线] → 限制改动只作用于 `cn_etf_beta` 的预算映射，不改 `cn_stock_trend_alpha_core` 主线口径。

## Migration Plan

1. 先修改 `cn-etf-beta-sleeve` spec，明确 V2 主候选池、并持数、fallback 与稳定器角色。
2. 再修改 `cn-a-portfolio-governor` spec，加入 ETF 稳定器预算映射与 under-deploy 证据要求。
3. 再修改 `backtest-research-audit` spec，把 ETF 稳定器的实际部署与 fallback 证据纳入正式 gate。
4. 实现时先以研究入口方式完成：
   - control：`cash fallback`
   - candidate：`511010 fallback + max_selected_symbols=2`
5. 跑最小 AB，优先验证实际暴露是否抬升，再比较收益风险。
6. 若 V2 部署改善但收益仍弱，则保留研究结论，不直接升级正式主线。

## Open Questions

- `511010` 在 V2 中是否应只作为唯一 fallback，还是保留 `cash` 作为并行对照组长期存在。
- ETF V2 并持 2 只时，默认采用：
  - 等权
  - 分数权重
  哪种更符合稳定器目标。
- Governor 对 ETF sleeve 的 V2 目标暴露应先用固定映射，还是用状态分段映射。
