## Context

当前 `A_STOCK_ETF_V1` 的组合主收益成立，但弱势环境下 ETF 腿缺少稳定、可解释的防守承接。现状不是“没有弱势规则”，而是存在弱势目标暴露时，经常因为通用 slot/cap 规则被压成 `effective_max_positions=0`，最终表现为不可部署或近似空仓。这个问题发生在 ETF beta sleeve 内部，不应通过放开 stock 腿、修改 regime 定义或重构组合 50/50 配比来掩盖。

约束条件：
- 这是防守层核心逻辑变更，必须保持单改动、可回滚、可审计。
- 不修改 `market-regime-framework` 的状态定义。
- 不修改 stock sleeve 的任何信号、排序、退出或预算逻辑。
- 不把反向 ETF 作为长期正式防守真相。

## Goals / Non-Goals

**Goals:**
- 为 ETF 腿在 `TRANS_DOWN` 与 `RISK_OFF` 下建立正式、单一真相的防守承接合同。
- 保证当防守资产可交易且弱势状态目标暴露大于零时，ETF 腿至少能形成 1 个可执行的防守 deploy seat。
- 明确弱势承接资产优先级、暴露上限与审计解释字段，使弱势配置可以被回放与解释。
- 保持 `BULL / TRANS_UP` 进攻段逻辑不变，避免一次 change 同时修改多个高风险变量。

**Non-Goals:**
- 不修改 stock 腿在弱势环境中的开仓规则。
- 不修改 combo 主结构或 50/50 配比。
- 不修改 regime 定义、状态切换阈值或 coarse state 语义。
- 不在本次 change 中引入新的长期主 API 结构。
- 不用反向 ETF、杠杆 ETF 替代正式防守资产池。

## Decisions

### Decision 1: 将“弱势承接”定义为 ETF sleeve 的独立正式合同
- 方案：新增 `etf-weak-state-defense-policy` capability，单独定义 `TRANS_DOWN / RISK_OFF` 的防守目标、资产优先级、deployability floor 与审计语义。
- 原因：当前问题不是普通 beta ranking 不够强，而是缺少正式的弱势部署合同。把它做成独立 capability，能避免弱势逻辑继续藏在 layering/fallback 细节里。
- 备选方案：直接在 `cn-etf-beta-sleeve` 里零散加条件。
- 不采用原因：会把弱势逻辑继续埋在 ETF sleeve 实现细节里，后续难审计、难回放。

### Decision 2: 优先修 deployability，不先抬高弱势总暴露
- 方案：当防守资产可交易且目标暴露大于零时，保留至少 1 个 deployable defense seat，并让最小可执行防守仓真正落地。
- 原因：当前最明显的失败点是“有目标暴露但无可部署槽位”，而不是“目标暴露太低”。先修 deployability 才能看清弱势承接的真实效果。
- 备选方案：直接上调 `RISK_OFF` / `TRANS_DOWN` 暴露上限。
- 不采用原因：会把“部署失败”伪装成“风险偏好提升”，结果难归因。

### Decision 3: 弱势资产优先级采用防守层级，而不是宽基兜底
- 方案：`RISK_OFF` 优先使用现金/货基/短债/利率债，其次黄金；`TRANS_DOWN` 才允许有限 defensive equity 或极小核心 beta。
- 原因：系统定位是个人多资产趋势配置系统，弱势阶段应该体现明确防守承接，而不是用宽基 beta 假装防守。
- 备选方案：继续以核心宽基作为主要 risk-off 承接。
- 不采用原因：会把 ETF 腿弱势段重新变成风险资产暴露，难以改善回撤路径。

### Decision 4: 审计面必须显式区分“可交易但被压零”和“无资产可承接”
- 方案：要求运行产物输出弱势策略层、选中防守资产类别、deployability 保底是否触发，以及未部署原因码。
- 原因：如果不区分这两类失败，后续无法判断是配置问题、预算问题还是资产池问题。
- 备选方案：只保留最终 target exposure。
- 不采用原因：不足以支持回放和策略评估。

## Risks / Trade-offs

- [风险] 防守资产池定义过宽，可能把本次单改动演化成新的 ETF 池扩张。
  - 缓解：本次只允许 formal defense candidates，新增资产必须由 spec 显式列举。
- [风险] deployability floor 可能在极弱市场下带来额外持仓，短期拖累收益。
  - 缓解：成功标准优先看 Sharpe / Calmar / MaxDD，不把 CAGR 提升设为本轮硬目标。
- [风险] 若实现时顺手修改了 stock 腿或 regime，结果将无法归因。
  - 缓解：tasks 明确禁止 touching stock sleeve 与 regime framework。
- [风险] 历史实验可能缺少新的弱势解释字段。
  - 缓解：新字段只要求出现在新运行产物，不要求历史产物回填。

## Migration Plan

1. 新增弱势承接 policy contract，并在 ETF sleeve runtime 中接入。
2. 保持 `BULL / TRANS_UP` 路径不变，只替换 `TRANS_DOWN / RISK_OFF` 的资产优先级与 deployability 规则。
3. 通过 `A_STOCK_ETF_V1` 与 ETF standalone 研究回放验证：先看弱势承接是否落地，再看组合风险指标是否改善。
4. 如果结果恶化，可直接回退 ETF weak-state policy 接入，恢复到现有 ETF sleeve 弱势部署逻辑。

## Open Questions

- 当前 formal defense candidate 集是否已经足够覆盖现金/短债/黄金三类承接，还是仍需先补资产池。
- `TRANS_DOWN` 是否需要允许极小核心 beta，还是先完全限制为 defense-only 更利于验证。
- 弱势 deployability floor 应绑定“至少 1 个 seat”还是“至少一个最小有效暴露阈值”，需要在实现前再定量化。
