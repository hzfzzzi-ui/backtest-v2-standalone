## 1. shadow mode 合同

- [x] 1.1 定义账户层 shadow mode 输入输出，DoD：明确 suggested budgets、actual budgets 和 deviation reasons；验证：spec 与设计文档能独立表达 shadow mode；风险：输出不完整会让后续上收预算缺解释基础。
- [x] 1.2 定义非接管约束，DoD：shadow mode 不得改变现有执行路径；验证：设计中明确 no-op on execution；风险：若 shadow mode 偷偷接管行为，会污染基线。

## 2. explain 与产物

- [x] 2.1 接入 runtime explain surface，DoD：`run_meta` 可读到账户层建议预算与实际预算差异；验证：产物字段命名和来源明确；风险：解释字段不足会让 Phase 2 无法对齐。
- [x] 2.2 保持当前基线行为不变，DoD：引入 shadow mode 后不修改 `A_STOCK_ETF_V1` 回测口径；验证：回放指标无漂移；风险：若行为漂移，shadow mode 失去意义。

## 3. 验收

- [x] 3.1 用主基线回放验证 explain 生效但行为不变，DoD：账户层建议预算可见、回测结果不变；验证：改前改后指标与 explain 对比；风险：若 explain 可见但结果漂移，需回滚。
