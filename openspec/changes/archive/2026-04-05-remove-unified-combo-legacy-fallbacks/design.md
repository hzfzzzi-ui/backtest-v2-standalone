## Context

经过前两轮 change，系统已经具备三个前提：
1. `component_source_contract` 已经稳定出现在编译结果与运行产物中。
2. 前端与后端都优先消费该合同对象。
3. 正确 replay anchor 仍稳定锁在 `A_STOCK_ETF_V1 -> cagr 0.13307783712519594`。

因此删除 fallback 的窗口已经打开。真正的风险不在“有没有新合同”，而在“删掉 legacy 入口后，是否还会误伤历史 baseline 回放”。所以这轮 change 的核心是 contract-only runtime + replay anchor gate，而不是再引入新的过渡层。

## Goals / Non-Goals

**Goals:**
- unified combo 编译路径只接受 `component_source_contract` 作为主运行来源。
- unified combo 运行服务只消费合同里的 `compile_input`。
- `research_custom_sleeves` 退为历史 provenance，不再参与当前主运行入口。
- `A_STOCK_ETF_V1` 结果保持不变。

**Non-Goals:**
- 本轮不改 stock/ETF 子腿策略本身。
- 本轮不改 `50/50` 组合公式。
- 本轮不重构 execution kernel 正式合同。

## Decisions

### 决策 1：删除 fallback，但保留历史 provenance 字段
- 主运行逻辑删除 fallback。
- 历史产物中已有的 `research_custom_sleeves` 与 legacy `sleeves` 字段不强制清洗，避免破坏历史可读性。

### 决策 2：以 replay anchor 做唯一验收
- 删除 fallback 后，必须继续复现 `A_STOCK_ETF_V1` 的目标结果。
- 如果 contract-only 路径无法复现，就说明当前 contract 信息还不完整，不能勉强删除 fallback。

## Risks / Trade-offs

- [风险] 合同对象仍有边缘 baseline 未覆盖 -> 缓解：先以 `A_STOCK_ETF_V1` 为门槛，再评估是否扩展更多基线回归。
- [风险] 历史 baseline 文件仍只含 legacy wrapper -> 缓解：编译入口允许读取 wrapper，但主运行输入必须落到 contract-only 对象后再继续。
- [风险] 删除 fallback 后排障难度上升 -> 缓解：保留 provenance 字段在产物中，供诊断层解释。
