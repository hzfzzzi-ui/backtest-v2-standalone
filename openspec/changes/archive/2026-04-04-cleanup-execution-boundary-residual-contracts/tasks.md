## 1. 正式边界收口

- [x] 1.1 收紧 `runtime-boundary-contracts`，只保留正式共享边界合同的外部定位。（DoD: spec 明确旧合同不再是正式共享对象；验证: `openspec validate cleanup-execution-boundary-residual-contracts` 通过；风险: 规格与当前兼容实现冲突）
- [x] 1.2 将 `candidate-plan-boundary-contracts` 明确降级为内部/迁移结构。（DoD: spec 场景覆盖内部定位；验证: delta spec 完整；风险: 调试链仍误用旧结构）

## 2. 残留清理准备

- [x] 2.1 定义执行边界残留清理的准入条件、回退顺序和验证基线。（DoD: 新 capability spec + design 对齐；验证: 文档可直接指导 cleanup 实现；风险: 清理顺序不清）
- [x] 2.2 将 `dead-code-removal` 收紧到“替代路径稳定后再删”。（DoD: delta spec 明确清理前提；验证: 场景可测试；风险: 借清理名义做大改）
