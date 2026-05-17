## Context

现有 rotation replacement 分两层完成：

- `candidate_plan` 根据候选分数和持仓分数生成替换 pair，并把 `ROTATION_REPLACE` 卖信号返回给执行内核。
- `execution_orders` 先处理所有卖信号，再根据计划候选生成买单。

B1 AB 中出现了计划替换卖出多于同日替换买入的情况，说明卖出与买入缺少原子合同。

## Decision

在 `execution_orders` 层实现原子合同，因为只有这一层同时知道：

- 当前真实持仓和现金；
- 正常卖单执行后的可用现金；
- 替换候选的实际买入数量、成本和现金可承受性；
- 最终进入订单集的卖单和买单。

执行顺序调整为：

1. 普通卖单照常先处理。
2. `ROTATION_REPLACE` 卖单不立即执行，先按 `rotation_candidate_symbol` 暂存。
3. 遍历买入候选时，如果候选携带 `rotation_pair`：
   - 找到对应暂存卖单；
   - 用“当前现金 + 对应卖出 proceeds”评估候选买单是否可执行；
   - 如果买单可执行，则同时写入 replacement 卖单和买单；
   - 如果买单不可执行，则两边都不写入订单集，并记录取消原因。
4. 普通买单仍沿用原有 slot、现金和数量约束。

同时在严格向量 runtime 的 T+1 fill 前增加二次过滤：

1. 对同日 pending orders 识别 replacement sell/buy pair。
2. 用真实 fill 成本口径模拟卖出净 proceeds、买入净成本和当日现金。
3. 如果 pair 买入在 fill 口径下不可执行，则在进入 fill 循环前同时移除卖单和买单。
4. 普通订单不受该过滤影响。

## Non-Goals

- 不在本 change 中实现主题保护 B1。
- 不新增 ETF 或行业主题标签输入。
- 不改变买入成本估算、lot 约束、滑点佣金语义。
- 不把 shadow plan 或预计算结果接入 runtime。

## Audit Fields

`debug_plan` 应暴露以下字段：

- `rotation_replace_planned_count`
- `rotation_replace_executed_pair_count`
- `rotation_replace_cancelled_count`
- `rotation_replace_cancelled_pairs`
- `rotation_replace_count` 应表示最终执行 pair 数，而不是候选计划 pair 数。
- 严格向量 runtime 不应在 `orders.csv` / `portfolio_trades.csv` 中留下孤立的 `ROTATION_REPLACE` 卖单。

## Risks

- 与历史 study 结果不可直接比较，因为启用 replacement 的路径行为会更严格。
- 如果执行内核中仍存在其他来源的 `ROTATION_REPLACE` 卖信号，必须按同一合同处理。
- 若 candidate_plan 未来支持多候选对同一持仓，需要继续保证 pair key 唯一。

## Rollback

回滚本 change 的代码，或在研究配置中保持 `rotation_replace_enabled=false`。正式基线默认不启用该功能，因此默认 baseline 不受影响。
