## Context

第一条 change 已经把 stock alpha 因子目录和 factor snapshot 做成正式研究产物，第二条 change 已经把账户层连续状态分数与状态快照做成正式研究产物。但这两层目前仍停留在“各自能独立研究”，尚未成为 research runtime 的正式输入合同。结果是：运行研究时仍容易直接重算因子和分数，导致研究平台无法真正做到 snapshot 为单一真相。第三条 change 的任务，就是把 research runtime 改成“先有 snapshot，再跑研究”的消费模式。

## Goals / Non-Goals

**Goals:**
- 为 research runtime 建立 snapshot input contract。
- 让 study runner 能声明并消费 factor/state snapshot。
- 让研究结果带上 snapshot lineage、source trace 和输入窗口信息。
- 保持主策略 runtime 不受影响。

**Non-Goals:**
- 不修改正式主线的预算、执行和账户状态消费。
- 不在本次 change 中重新设计 factor/state 的计算公式。
- 不把 snapshot-backed runtime 直接推广为正式主线默认模式。

## Decisions

### 1. research runtime 只消费已冻结 snapshot，不在消费侧重算研究逻辑
原因：平台因子化的核心目标就是把研究对象从运行链路中拆出来，保持 snapshot 为单一真相。

备选方案：runtime 在缺失 snapshot 时自动回退重算。
不选原因：会重新引入口径漂移，削弱 snapshot 的治理价值。

### 2. factor snapshot 与 state score snapshot 使用统一的 runtime 输入外壳
原因：后续研究 runtime 不应该为 stock factor 和 account state 各维护一套完全独立的输入协议。

备选方案：分别做两套独立 runner。
不选原因：会扩大维护面，不利于后续多资产扩展。

### 3. snapshot lineage 必须进入研究输出
原因：没有 lineage，snapshot-backed runtime 只是换了一层文件输入，不能满足可审计要求。

备选方案：只记录 snapshot 路径，不记录 lineage 字段。
不选原因：结果回溯和研究审计信息不够硬。

### 4. 本次 change 只接 research runtime，不接正式 runtime
原因：当前还处在平台因子化阶段，先稳定研究合同，再谈正式主线接线。

备选方案：同时接 research runtime 和正式主线。
不选原因：会把第三条 change 扩成不可归因的 L3 大改动。

## Risks / Trade-offs

- [风险] snapshot 输入协议定得过死，后续多资产扩展受限 → [缓解] 首版只固定最小公共字段，保留扩展字段空间。
- [风险] 研究 runtime 与前两条 change 的产物字段脱节 → [缓解] 明确要求 runtime 直接消费现有 snapshot 列结构，不另起字段体系。
- [风险] 用户误把 snapshot-backed runtime 当成正式主线入口 → [缓解] 在 spec 和 notes 中明确 research-only 边界。
- [风险] lineage 字段不足以覆盖审计 → [缓解] 首版强制包含 snapshot path、config hash、window、variant 和 source trace。

## Migration Plan

1. 建立 snapshot-backed runtime 输入协议。
2. 扩展 study runner，使其能消费 factor/state snapshot。
3. 为最小 demo study 补 snapshot-backed 研究样例和 focused tests。
4. 本次不迁移正式主线；若失败，直接回退新增 research runtime 模块、示例和测试。

## Open Questions

- snapshot 引用是否统一使用路径，还是要支持 artifact key + path 双轨。
- 第三条 change 的输出里是否需要统一 machine bundle 命名，避免 factor/state 两套术语并行过久。
- 后续若接正式 runtime，是否允许 snapshot 缺失时显式 fail-fast。
