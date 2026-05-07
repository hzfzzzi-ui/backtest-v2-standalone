## Context

当前主线里最像真实收益来源的是生命周期管理和退出规则，但研究层仍然主要以“当日候选上下文”来解释失败风险。第一版 `breakout failure / exit fragility` 研究面主要覆盖了 breakout 当天的 margin/quality/fade 等特征，没有覆盖 entry 之后的持有演化，因此无法回答下面三个核心问题：

1. 哪类 entry 在持有早期最容易从潜在赢家演化成坏仓。
2. 哪类持有上下文最容易触发 `pre_profit_breakout_failure`、`low10_exit`、`risk_off_exit`。
3. 当前主线收益到底来自 entry alpha，还是来自及时识别并剔除脆弱持仓。

要继续个股分析，下一步不能再只拆 rank，而必须把生命周期 / 退出风险做成独立 research surface，并且保持与当前股票腿主线锚点一致。

## Goals / Non-Goals

**Goals:**

1. 定义第二版生命周期 fragility catalog，覆盖持有早期衰减、弱 carry、破位风险和退出前脆弱性。
2. 生成与主线基线锚定一致的 lifecycle fragility snapshots 和 factor score snapshots。
3. 提供三窗口主线锚定 study surface，用于分析生命周期 fragility 与退出结果的关系。
4. 保持研究面与主线真实退出语义对齐，但不直接改动 runtime。

**Non-Goals:**

1. 不修改任何正式 exit 规则。
2. 不把 lifecycle fragility 直接接成主线 veto、rank 或强制退出。
3. 不在本轮同时重做 `Risk Gate`、`final_score` 或 ETF / defense 研究。
4. 不在本轮把持有期研究推广成新的主线因子候选结论。

## Decisions

### 1. 第二版研究对象从“breakout 当日特征”改成“持有期演化特征”

决策：
- 第二版 catalog 以 entry 后持有期上下文为主，而不是继续堆 breakout 当天特征。

原因：
- 当前主线收益并不主要来自当日排序，而更像来自后续持有与退出管理。
- 如果仍停留在 breakout 当日特征，无法解释主线真实收益链。

替代方案：
- 继续沿用第一版 fragility 特征，只增加阈值和加权。
- 放弃原因：这只会重复第一版弱结论，不能推进解释力。

### 2. 研究对象按“early fade / weak carry / break-floor / exit-conditional”四组组织

决策：
- 第二版 catalog 分四组：
  - early fade：入场后早期衰减
  - weak carry：持有期缺乏持续性
  - break-floor：跌破持有质量底线
  - exit-conditional：与真实 exit reason 对齐的上下文风险

原因：
- 这四组更贴近当前主线收益与退出规则的真实语义。

替代方案：
- 只做“失败风险总分”。
- 放弃原因：会把不同失败机理混成一团，后续无法归因。

### 3. study surface 默认按“失败风险 / 退出条件”口径，不预设为正向 rank

决策：
- 研究输出优先支持：
  - failure bucket
  - exit-conditional distribution
  - veto/fragility improvement
- 不预设 `higher is better`。

原因：
- 生命周期 fragility 更像负向条件与失败风险，而不是正向 alpha 因子。

替代方案：
- 直接按普通 IC rank 因子处理。
- 放弃原因：会再次把因子角色弄错。

### 4. 研究面仍然只锚定当前股票腿基线

决策：
- 本轮继续锚定当前认可的股票腿基线，不扩到组合主线、ETF 或 defense。

原因：
- 先把个股主线收益来源拆清，再谈组合层。

替代方案：
- 同时做组合层 lifecycle 研究。
- 放弃原因：会把 stock-only 生命周期问题和组合配置问题混在一起。

## Risks / Trade-offs

- [风险] 生命周期特征需要持有期轨迹，对 snapshot 口径要求更高。  
  → 缓解：所有 snapshot 必须显式记录 baseline 锚点和 as-of 语义。

- [风险] 第二版 fragility 仍可能只得到解释层结果，得不到强策略因子。  
  → 缓解：本轮只追求研究解释力，不追求直接生成主线候选因子。

- [风险] 与第一版 fragility、Risk Gate、execution pressure 存在边界重叠。  
  → 缓解：catalog 里明确每个对象属于生命周期风险还是参与门控，不混角色。

- [风险] 如果研究面过宽，后续 apply 会再次失去最小改动边界。  
  → 缓解：tasks 分成 catalog、snapshot、study 三组，先完成最小闭环。

## Migration Plan

1. 新建 research-only catalog/snapshot/study surface。
2. 用当前股票腿基线做三窗口真实研究。
3. 只根据研究结果决定是否需要第三版 fragility 或策略 A/B。
4. 如果后续研究失败，只需删除 research surface，不影响主线 runtime。

## Open Questions

1. 第二版是否需要把持有天数分层作为默认 study 输出。
2. `risk_off_exit` 应该归入 account context，还是继续作为 stock lifecycle 的 exit-conditional 对象。
3. 是否需要单独补一组“误杀好仓”研究指标，而不是只看失败风险。
