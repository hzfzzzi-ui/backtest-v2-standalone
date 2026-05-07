## Context

当前系统已经完成 `Account Allocator V2` 的 runtime cutover，账户层预算已经是主真相，旧 combo 结构已降为 reference。现阶段最值得研究的不是继续修改执行路径，而是定义 `RISK_OFF` 下账户层到底应该如何分配防守预算和左侧累积预算。

## Goals / Non-Goals

**Goals:**
- 只在账户层定义 `RISK_OFF` 的左侧累积预算语义。
- 明确 `RISK_OFF` 下 `defense` 与 `core_beta` 的目标配比，固定为“债为主、核心宽基次之”。
- 让 explain / audit 能明确说明这是账户层左侧累积，而不是 ETF 局部补丁行为。
- 保持研究归因干净，避免把预算改动与执行约束改动绑在一起。

**Non-Goals:**
- 不修改 `TRANS_DOWN` 预算曲线。
- 不修改 `stock alpha` 内核。
- 不修改 `state-edge cash release`。
- 不在本轮处理 lot / cash / top-up execution constraint。
- 不引入新市场或新资产类别。

## Decisions

1. 只改 `RISK_OFF`，不同时碰 `TRANS_DOWN`
- 原因：先解决最弱环境下“不要完全空仓”的账户行为问题，保持单变量。
- 备选方案：同时调整 `TRANS_DOWN`。放弃原因：会让行为归因混乱。

2. 左侧累积预算只允许 `债 + 510300.SH`
- 原因：当前研究目标是“债为主、少量核心宽基”，先不用黄金和第二核心宽基扩变量。
- 备选方案：加入 `510050.SH` 或黄金。放弃原因：会增加解释复杂度。

3. 先改目标预算，不改执行约束
- 原因：上一轮已经证明真正的执行阻塞可以单独识别；这轮先验证账户层语义是否值得成立。
- 备选方案：预算和执行一起改。放弃原因：无法区分是预算结构改善还是执行放松带来的变化。

4. 保持总暴露不自动上调
- 原因：这轮先验证预算内部结构与仓位直觉，不把“更高风险承担”混进结果。
- 备选方案：同时上调 `RISK_OFF` 总暴露。放弃原因：会把本轮从结构研究变成收益实验。

## Risks / Trade-offs

- [风险] 预算语义改变但实际行为仍不动 → 缓解：本轮验收同时看 `run_meta/audit` 结构和 `RISK_OFF` 实际持仓率。
- [风险] 核心宽基 30% 使弱势回撤加深 → 缓解：优先看 `MaxDD/Calmar`，不以 `CAGR` 为首要目标。
- [风险] explain 切到账户层后前端仍沿用旧 governor 文案 → 缓解：同步结果面 model 和 audit evidence。
- [风险] 用户误以为这轮已经解决执行落地问题 → 缓解：在 design/spec 中明确本轮不处理 execution constraint。
