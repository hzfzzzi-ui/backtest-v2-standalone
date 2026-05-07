## Context

当前系统已经完成账户层 runtime cutover，`RISK_OFF` 的账户级左侧累积预算也已经进入主解释，但最近一轮研究表明：预算语义成立，实际执行行为没有变化。根因已经从 ETF 局部 patch 收敛到账户层预算缺口没有被 materialize 为正式执行意图，典型表现为旧仓位延续、现金未释放、预算偏差长期停留在 explain 层。

## Goals / Non-Goals

**Goals:**
- 只在 `RISK_OFF` 下定义账户层预算如何触发真实执行落地。
- 让 defense / core beta 预算缺口能够转成正式执行意图，而不是只停留在 explain。
- 在不提高总暴露的前提下，允许账户层先做有限的去风险释放现金，再按预算顺序落地买入。
- 保持审计与 explain 能明确区分“预算成立但未执行”和“预算已进入执行”。

**Non-Goals:**
- 不修改 `TRANS_DOWN`。
- 不修改 `stock alpha` 内核。
- 不上调 `RISK_OFF` 总暴露。
- 不重做 regime。
- 不扩展到多核心宽基、多防守资产或新市场。

## Decisions

1. 只处理 `RISK_OFF`，不同时碰 `TRANS_DOWN`
- 原因：先解决最弱环境下账户层预算如何落地，保持单变量。
- 备选方案：一起处理 `TRANS_DOWN`。放弃原因：会重新把研究归因打散。

2. 采用“账户层 partial de-risk -> cash release -> budget-constrained rebalance”
- 原因：当前主要卡点不是目标预算，而是旧仓未释放现金、预算缺口无法进入执行链。
- 备选方案：继续沿用 ETF 局部 cash drip/top-up。放弃原因：之前已经证明这会把问题继续压在局部执行层。

3. defense 先于 core beta materialize
- 原因：当前 `RISK_OFF` 的正式预算语义仍是防守优先，核心宽基只是少量左侧累积。
- 备选方案：同步按 70/30 立即落单。放弃原因：在 lot / cash 受限时不利于稳定落地，也不符合防守优先。

4. 保持总暴露不自动上调
- 原因：这轮目标是“预算转执行”，不是“多承担风险”。
- 备选方案：允许 `RISK_OFF` 提高暴露上限。放弃原因：会把行为改善和风险提升绑死在一起。

## Risks / Trade-offs

- [风险] 账户层 release 过强，导致 `RISK_OFF` 下过度换手 → 缓解：限定为 bounded partial release，并保留 reason code。
- [风险] defense 优先导致核心宽基累计仍偏慢 → 缓解：明确把这轮定义为 execution materialization，不把累积速度当成首要目标。
- [风险] 预算一旦进入执行链，收益和回撤会变化 → 缓解：本轮验收标准改为“偏移可归因且符合账户层目标”，不再用“完全不漂移”约束。
- [风险] 解释面与实际行为不同步 → 缓解：统一写入 `run_meta`、`audit`、frontend governor/account allocator explain。

## Migration Plan

1. 在账户层 runtime 中新增 `RISK_OFF` budget materialization contract。
2. 将该 contract 接入 ETF 执行主路径，但只在 `RISK_OFF` 生效。
3. 允许账户层触发 bounded partial de-risk 释放现金，再按 defense → core beta 顺序落地。
4. 回放 `A_STOCK_ETF_V1`，先看结构，再看 `MaxDD / Calmar / RISK_OFF 非零持仓率`。
5. 若只形成 reject-only 行为，则按 no-go 记录并关停，不伪装成成功能力。

## Open Questions

- bounded partial release 的上限是沿用当前固定比率，还是需要新的账户层参数。
- defense 与 core beta 的最小可执行单位是否需要显式上收到账户层合同。
- 当前 `candidate_plan` 的既有持仓 top-up / reduce 规则，是否足够表达账户层 release 意图。
