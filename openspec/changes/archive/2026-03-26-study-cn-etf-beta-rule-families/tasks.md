## 1. 研究对照组与基础规则

- [x] 1.1 固定当前 ETF V1 规则为正式对照组；DoD：形成可复用的对照 study/preset 与结果引用；验证：能复现当前 V1 ETF 实验并输出统一 run_meta/audit；风险：旧配置字段漂移导致对照组不稳定。
- [x] 1.2 实现 `Dual Momentum 基础版` 的最小研究入口；DoD：支持 `510300/510050` 二选一、绝对过滤、`511010` 或现金 fallback；验证：study 能运行并输出 orders/nav/audit；风险：fallback 语义与当前 Governor 预算边界混淆。

## 2. 基础版最小 AB 与审计

- [x] 2.1 跑基础版最小 AB；DoD：至少完成 `空仓 fallback`、`511010 fallback`、`MA120` vs `12M>0` 三组对照；验证：产出 perf 对比表与 summary；风险：同时改变多个维度导致结果不可归因。
- [x] 2.2 补基础版审计证据；DoD：research audit 能证明绝对过滤和 fallback 是否生效；验证：audit.json 中出现 fallback 类型、触发次数、reason code 引用；风险：规则生效但缺少产物证据。

## 3. 缓冲带规则族

- [x] 3.1 实现 `Dual Momentum + 缓冲带` 最小版本；DoD：至少支持最小持有期、排名差阈值或双周频中的一种明确缓冲机制；验证：study 运行后可观察到未切换样本或换手下降；风险：缓冲逻辑写成黑箱导致无法解释未换仓原因。
- [x] 3.2 跑缓冲带 AB；DoD：与基础版在同候选池、同 fallback、同窗口下完成最小对照；验证：输出换手、交易数、Sharpe、MaxDD 对比；风险：缓冲机制过强导致几乎无交易。

## 4. Vol Target 规则族

- [x] 4.1 实现 `Dual Momentum + Vol Target` 最小版本；DoD：至少支持 `20D` 或 `30D` realized vol 缩放，并把缩放前后预算暴露到产物；验证：run_meta/audit 能看到 budget 变化与 vol 驱动来源；风险：仅在 provider 内缩放而没有对齐 Governor 语义。
- [x] 4.2 跑 Vol Target AB；DoD：与基础版在同候选池、同 fallback、同窗口下完成最小对照；验证：输出波动、回撤、预算缩放分布；风险：结果变化来自其他预算链路而非 vol target 本身。

## 5. 路线收敛与结论

- [x] 5.1 汇总三组规则族研究结论；DoD：形成统一 compare 表，明确哪组值得进入下一轮正式实现；验证：summary/report 能回答“规则是否生效”和“是否值得推进”；风险：只看收益不看审计与稳健性。
- [x] 5.2 明确回退与不推进口径；DoD：若某组规则族不值得继续，文档中明确标记为不建议推进；验证：change 实现说明包含回退路径与弃用理由；风险：研究结论模糊，后续又重复开启同类试错。
