## Context

当前 runtime 的候选排序入口有明显的历史命名债：`mf_rank`、`mf_score` 这些名字最初指向 multifactor/moneyflow，但在当前 breakout/runtime 实现里，排序输入已经被 `final_score` 覆盖。用户与研究层已经开始把真正的 moneyflow 因子单独研究，如果 runtime 继续沿用 `mf_rank`，同一个名字将同时指代两套不同语义。

## Goals / Non-Goals

**Goals:**
- 为 runtime 建立 canonical 的 `final_score_rank` 语义。
- 在不改变策略行为的前提下，统一 candidate audit、debug plan、daily diagnostics 和聚合 counters 的正式命名。
- 对旧字段保留兼容别名，降低对历史实验和旧脚本的冲击。

**Non-Goals:**
- 不重写排序算法。
- 不移除旧配置键或旧产物列。
- 不把真正的 moneyflow 因子接入 runtime。

## Decisions

### D1. 采用“新 canonical + 旧 alias”而不是硬替换
- 选择：新增 `final_score_rank*` / `final_score_value`，同时继续写出 `mf_rank*` / `mf_score`。
- 原因：当前仓库大量测试、脚本、历史产物都依赖旧名字；硬替换会制造无关口径漂移。
- 备选：直接全仓改名。未选，因为影响面太大且无法一次性回收所有历史依赖。

### D2. 先治理边界输出，不强行重命名所有内部变量
- 选择：优先改 candidate audit、debug plan、daily row、metrics counter、artifact diagnostics 的正式字段。
- 原因：真正需要稳定的是运行边界与解释面；内部变量可逐步清理。
- 备选：一步到位改内部全部函数/参数名。未选，因为风险高、收益低。

### D3. 聚合层优先消费新字段，缺失时回退旧字段
- 选择：artifact diagnostics 和 metrics 聚合读新字段，缺失时兼容旧字段。
- 原因：这样新产物立即形成正式语义，旧产物仍可读。
- 备选：只写新字段不读旧字段。未选，因为会打断旧实验分析。

## Risks / Trade-offs

- [风险] 字段双写会让 daily/candidate schema 变宽。→ 通过只增加少量 canonical 别名，并在 spec 中明确新旧主次关系控制复杂度。
- [风险] 测试和脚本仍继续使用旧字段。→ 通过兼容保留旧字段，并逐步把测试断言迁到新 canonical 字段。
- [风险] 用户误以为 moneyflow 因子已进入 runtime。→ 通过 proposal/spec 明确：此次只做 runtime 命名治理，不引入 moneyflow 研究逻辑。
