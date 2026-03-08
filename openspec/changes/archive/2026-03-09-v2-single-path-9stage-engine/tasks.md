## 1. Stage 契约与时点边界
- [x] 1.1 新建 `stage_pipeline` 模块骨架，以及 `DayContext`、`PortfolioState`、`DataBundleView`、`StageInputs/StageOutputs` 契约。
- [x] 1.2 为 `DataBundleView` 加时点可见性保护，明确 `t` 日盘后与 `t+1` 日开盘的数据边界。

## 2. 单路径 9-stage 壳
- [x] 2.1 实现固定顺序的 stage pipeline shell 与 collector，落地 `S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S9 -> S8 -> S7`。
- [x] 2.2 为候选流、持仓流和 `S7` 合流点建立最小 adapter，先包裹现有 legacy 信号、退出、风控与下单规划逻辑。
- [x] 2.3 落实 stage 禁用时的 neutral output 规则，禁止因开关变化切换到另一条执行路径。

## 3. 公开主线路由与产物协议
- [x] 3.1 将 `experiment_runner` 与当前 `foundation shell` 的公开入口切到 stage pipeline shell，并把 legacy orchestrator 降级为 adapter / execution kernel。
- [x] 3.2 新增 `stage_summary.json`，并把 `stage_summary`、`stage_pipeline` 摘要接入 `manifest.json`、`run_meta.json` 和 `audit.json`。

## 4. 基线门禁与旧层冻结
- [x] 4.1 以 `exp_20260308_021045840_cde0` 为锁定基线，对 stage pipeline shell 做等价验证。
- [x] 4.2 更新旧编排冻结清单，明确哪些 legacy 路由仍被 stage adapter 使用，哪些公开路由已冻结、禁止继续扩展。
