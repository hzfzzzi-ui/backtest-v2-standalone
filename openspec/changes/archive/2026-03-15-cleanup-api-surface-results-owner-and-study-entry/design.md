## Context

当前仓库已经完成了三轮主干重构：API 命名空间拆分、执行总线统一、脚本面治理与 study runner 引入。系统主干已经形成，但桌面主路径仍残留几块影响长期演进的结构债：

- 前端主路径仍混用 `surface/section` 与 `/api/backtest_v2/artifacts/read`。
- 桌面结果区仍保留 fallback DOM 与 Vue workbench 并存的诊断路径。
- `ui-controls.js` 仍承担“表单 -> config draft -> runtime request”的高价值配置核心逻辑。
- 研究入口虽然已有 `study + generated thin script` 路线，但尚未成为默认主路径。

这轮设计的目标不是继续扩展功能，而是继续清理主路径，使系统更适合后续接入别类资产，同时严格保持 `baseline_V10_1 -> exp_20260314_144548534_7db9` 的回归结果不漂移。

主要约束：

- 不修改高风险执行核心的价格型信号时点与执行口径。
- 不在本次设计中重写 `breakout_signal_provider.py` 或 `strict_runtime_impl.py`。
- 前后端清理必须保持 `perf / orders / trades / nav` 对照稳定。

## Goals / Non-Goals

**Goals:**

- 让桌面前端主路径只消费 `manifest / surface / surface/{section}` 与少量专用接口。
- 让 Vue results workbench 成为桌面结果区唯一渲染 owner。
- 将 `ui-controls.js` 中的配置核心抽离为独立模块，使前端真相转向 `experiment manifest / runtime snapshot`。
- 将正式实验入口进一步收口到 `study + generated thin script`。
- 为未来接入多资产保留干净的 API 契约与前端结果面。

**Non-Goals:**

- 不重写执行总线与高风险回测主循环。
- 不修改 `baseline_V10_1` 的研究口径、交易规则、成本口径和时间对齐。
- 不在本次变更中解决所有历史研究脚本迁移，只收口正式主路径。
- 不追求一次性移除所有前端旧文件，而是继续把旧文件压成薄壳。

## Decisions

### 决策 1：桌面主路径废弃通用 `artifacts/read`

主路径 API 读取方式固定为：

```text
manifest
  -> surface
  -> surface/{section}
  -> 少量专用接口
```

`/api/backtest_v2/artifacts/read` 仅允许作为极少量非主路径的运维/调试工具，不再作为桌面研究页的正常读取方式。

原因：

- 前端不应继续理解后端 artifact 物理布局。
- 多资产接入时，前端若依赖文件名/路径，会被当前 A 股产物结构锁死。
- `surface/section` 是更稳定的契约边界。

备选方案：

- 保留 `artifacts/read` 作为主路径读取手段。
  - 否决原因：短期方便，但会继续把 artifact 内部结构暴露给前端。

### 决策 2：删除生产主路径中的 fallback 结果 DOM

桌面结果区最终收敛为：

```text
desktop-research-page
  -> ResultsWorkbenchSnapshot
  -> Vue results workbench
```

生产主路径不再保留可见 fallback DOM。结果渲染唯一 owner 是 Vue workbench。

原因：

- 双轨结果面会持续制造 DOM ownership 不清、前端重复渲染和结果语义漂移。
- 新资产接入时，不应再同时适配“旧 DOM 面板”和“新 workbench”两套结果面。

备选方案：

- 保留 fallback DOM 作为 mount 失败时兜底。
  - 否决原因：会延长双轨结构寿命，增加后续扩展成本。

### 决策 3：前端运行真相转向 manifest / runtime snapshot

前端不再长期以 `config_id` 为页面主语义，而是以：

- `experiment manifest`
- `runtime snapshot`
- `ResultsWorkbenchSnapshot`

作为结果和运行状态的真相。配置继续存在，但退回为输入来源之一。

原因：

- `config_id` 更像当前 A 股研究平台的管理语义，不够资产无关。
- `manifest / snapshot` 更适合未来统一描述股票、ETF、期货或其他资产的运行输入与结果。

备选方案：

- 继续以配置中心和 `config_id` 驱动桌面页状态。
  - 否决原因：长期会让前端继续绑死配置治理逻辑。

### 决策 4：优先抽离配置核心，而不是先做 UI 提示清洁

`ui-controls.js` 的优先拆分对象是“表单 -> config draft -> runtime request”的配置核心逻辑，而不是先拆控件 hint 或显示提示。

原因：

- 这是前端最接近运行语义和未来多资产扩展的关键点。
- 继续把配置编译逻辑留在 `ui-controls.js` 中，会阻碍长期演进。

备选方案：

- 先拆 hint、badge、visibility 等轻量 UI 逻辑。
  - 否决原因：风险更低，但无法解决真正的扩展性问题。

### 决策 5：研究主路径默认收口到 `study + generated thin script`

未来正式实验入口默认走：

```text
.study.yaml
  -> backend.cli study_run
  -> backend/scripts/generated/run_<study_id>.py
```

不再鼓励新增顶层大型研究脚本。

原因：

- 这与“AI 先接总线，再定义 study，再生成统一薄脚本”的工作方式一致。
- 有利于实验归因、治理和审计。

备选方案：

- 长期保留顶层 wrapper 作为主要实验入口。
  - 否决原因：容易重新长回脚本面第二套系统。

## Risks / Trade-offs

- [前端结果面完全移除 fallback DOM] → 需要确保 Vue workbench 主路径稳定，先以静态与集成测试卡住结果 owner。
- [配置核心抽离会触碰运行请求结构] → 拆分时必须保持请求 payload 不变，并以前后对照 `baseline_V10_1` 复核。
- [API surface 收口可能导致前端读取路径大面积变化] → 先保留专用 section 接口，再逐步清主路径中的 `artifacts/read` 调用点。
- [study 主路径收口会降低临时脚本自由度] → 保留 generated thin script 作为 AI 和人工可直接运行的薄入口。

## Migration Plan

### Phase 1：API Surface 收口

- 盘点桌面主路径对 `/api/backtest_v2/artifacts/read` 的调用点。
- 为这些调用点补齐 `surface / section / 专用接口`。
- 让 `artifacts.js` 和 `backtest_v2.js` 主路径只消费 canonical read model。

### Phase 2：结果工作台单 owner 化

- 删除 `wbResultsFallbackRoot` 相关生产主路径逻辑。
- 清理 `Fallback only` 的旧 DOM 渲染路径。
- 固定 `desktop-research-page -> snapshot -> Vue workbench`。

### Phase 3：配置核心抽离

- 从 `ui-controls.js` 提取 config draft core。
- 让旧控制器只保留控件联动与展示提示。
- 让页面主状态从 `config_id` 驱动转向 manifest / snapshot 驱动。

### Phase 4：study / thin script 主路径收口

- 将高频主线研究脚本继续迁入 `.study.yaml`。
- 扩大 `backend/scripts/generated/` 的正式入口角色。
- 用 inventory 与 governance 测试阻止新的顶层大型研究脚本回流。

### 回滚策略

- 每一阶段结束后都以前后对照 `baseline_V10_1 -> exp_20260314_144548534_7db9` 复核。
- 若某阶段导致 `perf/orders/trades/nav` 漂移，则仅回滚该阶段，不跨阶段混合回滚。

## Open Questions

- `artifacts/read` 在最终状态下是否完全删除，还是保留极少量运维/调试用途。
- 配置核心抽离后，前端是否需要引入更明确的 `config draft core` 单测层，而不是继续依赖页面级边界测试。
