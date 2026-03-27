## Context

当前宽基 ETF 独立主线已经完成了两类尝试：

- 暴露语义与 controlled accumulation 改造
- Governor 边界与 ETF 本地决策拆分

但真实结果仍停留在 `2%~3% CAGR` 附近，且长期存在 `UNDERDEPLOYED`。现有审计证据已经说明，继续单独调 `LIGHT / TRANS_DOWN` 的暴露翻译不是主矛盾；更明显的瓶颈是：

- `absolute filter` 过严导致大量 `NO_ELIGIBLE_AFTER_ABSOLUTE_FILTER`
- 候选池本身可能偏弱、过窄，或 proxy 替换失真
- 选择链路可能把强 ETF 拦在最终持仓之外

因此这轮设计不再扩 exposure policy，而是把宽基 ETF 主线研究严格限定到这三条主瓶颈。

## Goals / Non-Goals

**Goals:**

- 固定 Governor/CTA 边界与 ETF 本地暴露语义，只研究绝对过滤、候选池、选择链路。
- 为宽基 ETF 主线建立顺序化研究矩阵，确保每轮只改一个主变量。
- 在产物和 audit 中显式回答：
  - 绝对过滤挡掉了多少机会
  - 候选池 profile 是否偏弱
  - 排序/选择链路如何决定最终持仓
- 为下一轮是否继续推进 ETF 主线提供更可靠的归因依据。

**Non-Goals:**

- 不研究行业 ETF、主题 ETF 或个股 alpha 组合。
- 不新增新的 Governor 暴露语义 family。
- 不在本轮实现 unified runtime，也不讨论组合权重。
- 不把 `outputs/` 中的临时结果上升为新的源码契约。

## Decisions

### 决策 1：固定 Governor 边界与当前 ETF 暴露语义，避免变量继续漂移

本轮所有 AB 都以当前宽基 ETF 主线控制组为基准，Governor/CTA 真相、fallback contract 和本地受控承接语义保持不变。

原因：

- 现有证据已经说明，继续调 exposure policy 不是主矛盾。
- 如果这轮再混入暴露语义变量，结果仍然无法归因。

备选方案：

- 继续扩大 `LIGHT / TRANS_DOWN` 承接或 fallback 差异。
- 放弃，因为这会把研究重新带回已经验证过收益有限的路径。

### 决策 2：按“绝对过滤 -> 候选池 -> 选择链路”的顺序研究

本轮采用三段顺序化研究：

1. 绝对过滤族  
   控制候选池和选择链路不变，只比较过滤 profile：
   - `MA200 + 12M>0` 控制组
   - `MA200 only`
   - `MA150 + 12M>0`

2. 候选池族  
   固定过滤优胜者和选择链路，只比较候选池 profile：
   - `A0 proxy pool`
   - `proxy expanded pool`
   - `standard overlap pool`

3. 选择链路族  
   固定过滤优胜者和候选池优胜者，只比较选择链路 profile：
   - `global top2 12/6/3`
   - `global top2 6/3/1`
   - `core + growth slot`

原因：

- 这三点是当前最可能影响 ETF 收益的主瓶颈。
- 顺序化研究可以避免多变量同时变化。

备选方案：

- 一次性全矩阵搜索。
- 放弃，因为它会再次制造“收益有变化但无法解释”的结果。

### 决策 3：候选池仍限定为宽基/宽基风格 ETF，不引入行业 ETF

候选池 profile 只允许包含：

- 宽基 ETF
- 宽基风格/板块级 broad-based proxy，例如创业板、科创 50
- 标准中证 1000 / 红利 ETF 或当前 proxy

禁止纳入行业 ETF 或主题 ETF。

原因：

- 用户已经明确要求下一轮只研究宽基 ETF sleeve。
- 行业 ETF 会把风格敏感度和切换节奏问题带进来，破坏本轮归因。

### 决策 4：把瓶颈统计做成一等产物，而不是只看 perf

本轮新增/强化以下证据：

- `absolute_filter_reject_day_count`
- `absolute_filter_reject_reason_counts`
- `candidate_pool_profile`
- `candidate_pool_coverage_summary`
- `selection_chain_profile`
- `selection_chain_winner_counts`
- `selection_chain_reject_reason_counts`
- `underdeploy_reason_counts` 与上述三类统计的交叉摘要

原因：

- 不把瓶颈做成一等证据，就会再次回到“只看收益猜原因”。

备选方案：

- 只在 study 汇总里人工解释。
- 放弃，因为这不满足可审计性要求。

## Risks / Trade-offs

- [标准 ETF 覆盖窗口较短] → 统一在 overlap 窗口比较，避免把长窗口 proxy 与短窗口标准 ETF 混成同一结论。
- [provider 分支继续长胖] → 把 profile 定义收口到 contract/profile table，不在 provider 里继续写散乱硬编码。
- [过滤放松后回撤显著恶化] → 本轮验收不只看 CAGR，也看 `MaxDD / Sharpe / reject-day change / actual exposure`。
- [候选池扩张引入伪强势资产] → 先用受控 pool profile，禁止行业 ETF 和主题 ETF 混入。

## Migration Plan

- 本轮只新增 study profile、contract 字段和 audit 证据，不迁移已有 baseline。
- 若结果不成立，回退方式是撤回新增的 filter/pool/selection profile 和对应 audit 字段，保留当前控制组。

## Open Questions

- 如果过滤优胜者明显偏向更快的绝对过滤，是否还需要单独研究月频与双周频组合，这一轮先不回答。
- 如果 `global top2 6/3/1` 显著优于 `12/6/3`，是否意味着 A0 需要正式从慢链路迁移到更快的 ranking chain，这留到下一轮决策。
