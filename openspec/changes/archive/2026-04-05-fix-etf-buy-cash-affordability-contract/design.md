## Context

当前 ETF 独立主线已经完成两轮窄修：

- partial fallback target 修复，去掉了 fallback 被压成大额正仓位的错误语义；
- standalone deploy delta target 修复，去掉了 core BUY signal 被写成整仓目标的错误语义。

修复后，执行 lineage 暴露出新的主瓶颈：`exp_20260401_045408774_3961` 中 `generated_count=805`、`filled_count=55`、`rejected_count=750`，且 rejected terminal reason 全部是 `INSUFFICIENT_CASH`。这说明当前问题已经不在 ETF state contract，而在 BUY 订单从 planning 到 fill 的现金合同不一致。

现状是：

- execution kernel 在 `execution_orders.py` 中按 `qty * next_open` 与 `est_cash` 比较；
- fill 阶段在 `fill_accounting.py` 中按 `open*(1+slip) + commission` 扣减真实现金；
- 因此大量“planning 认为买得起”的订单，会在次日被整单拒绝。

本 change 的利益相关边界很窄：只修 BUY affordability contract，不触碰 ETF 选池、五状态语义、fallback 研究定位和 fill price 模型。

## Goals / Non-Goals

**Goals:**

- 让 execution kernel 与 fill 阶段对 BUY 现金可负担性的判断使用同一口径。
- 在 planning 阶段就裁掉或裁剪注定次日失败的 BUY 订单，减少假阳性的 `selected_count`。
- 保留整手约束，且让诊断能区分“planning 阶段现金不足”和“fill 阶段仍然异常拒绝”。
- 让 ETF `BULL / TRANS_UP` 的 under-deploy 分析重新可信。

**Non-Goals:**

- 不修改 ETF `BULL / TRANS_UP / RISK_OFF` 的状态语义与 target exposure。
- 不修改 ETF 资产池、absolute filter、growth slot 规则。
- 不改变 fill price、slippage、commission 的既有模型。
- 不引入部分成交或跨日保留 BUY 订单。

## Decisions

### 1. 用 fill 等价净成本替换 execution kernel 的 BUY affordability 口径

决策：

- execution kernel 计算 BUY 可负担性时，必须使用与 fill 阶段一致的净成本口径：`gross = qty * open * (1 + slip)`，`net = gross + commission`。

原因：

- 当前 planning 与 fill 使用两套不同成本口径，是 `selected_count` 与真实 fill 脱节的直接根因。
- 在 planning 阶段收敛口径，比在 fill 阶段继续“先放行后拒绝”更可审计。

备选：

- 保持 planning 不变，只在 fill 阶段拒绝：拒绝了真实问题，但继续污染 diagnostics，不采用。
- 在 fill 阶段改成强行成交：会破坏真实现金约束，不采用。

### 2. 当订单不可负担时，先按整手裁剪到最大可负担数量

决策：

- 对 BUY 订单先求最大可负担 lot 数；若仍至少一手，则生成裁剪后的订单；若不足一手，则在 planning 阶段直接 `SKIP_NO_CASH`。

原因：

- 当前大量订单只差 commission/slippage 就失败，整单拒绝会低估 deployability。
- 按整手裁剪比“强行全单成交”更符合 A 股 / ETF 交易现实，也比 fill 阶段临时改 qty 更容易保持审计一致。

备选：

- 不裁剪，只允许全单或拒绝：会继续制造大量 scheduled-but-rejected 假信号，不采用。
- fill 阶段再裁剪：会让 planning diagnostics 与 fill diagnostics 再次分离，不采用。

### 3. 诊断层新增 planning-vs-fill affordability 对账

决策：

- daily/accounting 与 execution lineage 必须能区分：
  - planning 阶段 `SKIP_NO_CASH`
  - fill 阶段 `INSUFFICIENT_CASH`
- 本 change 的回归门槛不是收益，而是显著压低“scheduled 但次日因现金不足被拒”的假阳性订单。

原因：

- 当前 ETF 的主问题已经是合同断层，必须优先恢复可解释性。
- 如果只改行为、不补诊断，下一轮仍无法判断 deployability 是被 slot、cash 还是 fill reject 卡住。

## Risks / Trade-offs

- [风险] 这会改变所有 BUY 路径的下单数量，而不只影响 ETF。  
  → 缓解：先用 execution kernel / fill accounting 单测锁定合同，再以 ETF 长窗为主验证；必要时补一个 A 股基线 smoke。

- [风险] 裁剪后成交次数可能上升，但单笔金额变小，短期可能压低 CAGR。  
  → 缓解：本 change 以合同正确性和诊断可信为第一目标，收益只做次级观察。

- [风险] 若 planning 使用的 next open 与 fill 实际使用的价格源仍有边界差异，可能残留少量 `INSUFFICIENT_CASH`。  
  → 缓解：允许少量剩余 reject，但要求大幅下降，并在 diagnostics 中明确可见。

## Migration Plan

1. 在 `order_sizing.py / execution_orders.py` 增加 fill 等价 BUY affordability 计算与整手裁剪。
2. 在 `fill_accounting.py` 保持真实扣现金逻辑不变，只补对账与测试。
3. 在 `daily_accounting.py` / audit 侧补充 planning-vs-fill reject 计数。
4. 先跑针对性单测，再重跑 ETF `2012-2026` 长窗。
5. 若结果异常，按文件回退本 change，并恢复原 execution kernel affordability 逻辑。

## Open Questions

- 是否需要把 affordability 头寸留白做成统一 buffer（例如显式预留最小 commission/slippage 余量），还是只按 fill 等价净成本精确裁剪即可。
- 是否需要把 `portfolio_candidates.csv` 中 `selected=True` 的 execution kernel 成功行一并补齐，避免继续依赖 daily diagnostics 间接观察。
