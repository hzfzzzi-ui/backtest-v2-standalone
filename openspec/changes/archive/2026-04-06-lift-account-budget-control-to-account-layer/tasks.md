## 1. 预算合同

- [x] 1.1 定义账户层 stock / ETF budget map，DoD：状态到 budget 的映射有正式合同；验证：spec 和 design 明确 budget 来源与 fallback 条件；风险：若 fallback 未定义，会影响现有基线回放。
- [x] 1.2 明确 `50/50` 降级为 fallback baseline，DoD：`50/50` 不再是唯一真相；验证：文档和 explain 表达一致；风险：若同时删掉 fallback，会放大迁移风险。

## 2. runtime 接管

- [x] 2.1 让账户层预算进入 runtime 编译真相，DoD：stock / ETF 实际预算来自账户层；验证：`run_config/run_meta` 可追溯 budget 来源；风险：预算来源混用会导致结果不可归因。
- [x] 2.2 保持 ETF 仍为单一运行腿，DoD：本 change 不拆 ETF defense/core beta；验证：diff 范围不进入 ETF 角色拆分；风险：若同时拆角色，会混淆后续 phase。

## 3. 验收

- [x] 3.1 用主基线回放验证账户预算已接管，DoD：explain 可见账户层预算，行为变化可归因；验证：改前改后 budget/explain/指标对比；风险：若行为变化无法归因，需要回滚。

