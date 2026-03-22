## 1. Diagnostics Contract 建立

- [x] 1.1 盘点 `daily_accounting.py / artifacts_diagnostics.py / strict_runtime_daily_loop.py` 现有计数来源，整理原始事件字段与最终 funnel 字段映射表。
- [x] 1.2 新增统一的 runtime diagnostics contract / dataclass，承接执行层原始 diagnostics input 与 stage count 归一化输入。

## 2. Daily Accounting 收口

- [x] 2.1 重构 `daily_accounting.py`，让它只产出 daily row 基础字段、accounting snapshot 和原始 diagnostics input。
- [x] 2.2 去掉 `daily_accounting.py` 里的 route 专属最终 funnel 归一化写法，保留必要的 route hint 但不直接定义最终 stage 语义。

## 3. Artifact Diagnostics 收口

- [x] 3.1 重构 `artifacts_diagnostics.py`，改为只消费 canonical diagnostics input 构建 buy funnel、counters 和 reason diagnostics。
- [x] 3.2 把 stage label、stage note、route-specific normalization 统一集中到 diagnostics builder，避免不同 artifact 重复定义。

## 4. Strict Runtime Daily Loop 收口

- [x] 4.1 收缩 `strict_runtime_daily_loop.py` 中与最终 diagnostics 语义混杂的内容，只保留执行事件与 debug plan 汇总边界。
- [x] 4.2 确认 default runtime daily loop 与 stage pipeline 之间的 diagnostics 交接边界，避免执行本体重新成为 diagnostics owner。

## 5. 回归与收口

- [x] 5.1 更新相关单测/集成测试，覆盖 canonical diagnostics input、buy funnel 与 counters 契约。
- [x] 5.2 跑 `baseline_V10.1 -> exp_20260314_144548534_7db9` 的 artifact compare 与 runtime smoke，确认收益、回撤、订单数、交易数和关键 stage diagnostics 不漂移。
- [x] 5.3 回写 OpenSpec 任务状态，并记录 diagnostics 归一化前后对照结论与回退点。
