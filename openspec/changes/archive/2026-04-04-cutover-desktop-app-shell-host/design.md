## Context

前端文档已经把目标态定义成新的单页 `desktop app`，并明确 `results-workbench` 只是 `results_workspace` 子模块。当前实现虽然修过加载链，也补了一部分 desktop-shell 状态骨架，但正式宿主仍由旧壳控制。

## Goals / Non-Goals

**Goals:**
- 让新桌面壳正式成为桌面端默认宿主入口。
- 固定单一 root mount、统一 app state 和统一 API adapter 约束。
- 明确旧壳和 bridge 的迁移退出条件。

**Non-Goals:**
- 不在本 change 中重写所有结果组件。
- 不在本 change 中做移动端交互重构。
- 不在本 change 中引入复杂路由。

## Decisions

- 决策 1：继续采用单页 app，不引入正式多路由。
  原因：这是已确认的正式文档方向，且当前性能更稳。

- 决策 2：结果 snapshot 归新桌面 app state 持有。
  原因：bridge 只是过渡层，长期保留会继续制造双真相。

- 决策 3：旧 `backtest_v2.js` 正式降级为迁移层，不再作为主 bootstrap owner。
  原因：这是前端完成态的必要条件。

## Risks / Trade-offs

- [风险] 宿主切换破坏加载链
  → 缓解：要求主工作流 `加载配置 -> 改参数 -> 运行 -> 看结果 -> 保存基线` 做回归基线。

- [风险] 新壳接管过慢导致旧壳继续长胖
  → 缓解：spec 明确旧壳只是迁移层，并要求退出条件。

## Migration Plan

1. 先在 specs 中收紧宿主入口、snapshot、API adapter 边界。
2. 再在实现阶段切换默认入口和 root mount。
3. 最后移除旧 bridge 与旧主 bootstrap。

## Open Questions

- 需要在实现前确认哪些旧 page controls 还必须保留一轮 compat。
