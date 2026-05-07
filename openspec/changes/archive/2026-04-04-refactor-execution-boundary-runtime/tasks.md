## 1. 正式合同收口
- [x] 1.1 将 `runtime-boundary-contracts` 收口到 `action_intent_v1 / risk_override_v1 / target_book_v1 / execution_audit` 的正式合同对象与最小回归基线。
- [x] 1.2 明确 `action_intent_v1` 的 `BUY/SELL` 尺寸语义、优先级语义和输入合法性，并补测试覆盖非法输入。

## 2. Governor 与持仓语义收紧
- [x] 2.1 将 `cn-a-portfolio-governor` 收口到 `subsystem_budget_v1` 与 `risk_override_v1` 的运行时主路径。
- [x] 2.2 将 `source-aware-holdings` 收口到 `SOURCE_ONLY` 与“普通卖出只卖自己来源仓位”的统一运行时约束。

## 3. 旧过渡壳降级
- [x] 3.1 将 `candidate-plan-boundary-contracts` 明确降级为子系统内部或迁移期结构，并从共享执行主路径移开。
- [x] 3.2 补 `execution-contract-goldens`，覆盖阻断、覆盖、截断、整手取整和优先级跳过。

## 4. 实现前置准备
- [x] 4.1 在 tasks 中列明迁移顺序与回退方式，保持 apply-ready 基线。
