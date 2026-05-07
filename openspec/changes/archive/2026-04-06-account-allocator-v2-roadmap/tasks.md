## 1. 总 change 骨架

- [x] 1.1 为 `Account Allocator V2` 写清最终目标架构，DoD：总 change 的 proposal/design/spec 明确描述账户中枢、三类预算角色与执行层职责；验证：总 change 文档可独立解释目标架构；风险：若目标仍模糊，分 change 会再次分叉。
- [x] 1.2 写清分 change 列表和依赖顺序，DoD：shadow mode、预算上收、现金释放、ETF 预算拆分、runtime cutover 的先后关系明确；验证：后续分 change 可直接引用；风险：阶段边界不清会导致实现绑在一起。

## 2. 迁移纪律

- [x] 2.1 明确总 change 不直接承载实现，DoD：本 change 只定义架构和阶段，不直接改运行时代码；验证：任务列表不包含代码实现项；风险：总 change 若直接承载实现，会失去“总分”价值。
- [x] 2.2 明确各分 change 的验收重点，DoD：每个分 change 都有单独验收口径；验证：迁移顺序和回滚路径可从总 change 读出；风险：如果验收边界不清，后续结果无法归因。

