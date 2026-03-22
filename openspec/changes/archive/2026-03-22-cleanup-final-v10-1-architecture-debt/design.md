## Context

当前仓库已经完成多轮边界收口，`baseline_V10.1` 也已成为唯一正式研究锚点，但主干代码中仍残留三类影响长期演进的结构债：

1. 前端仍同时维护“配置来源语义”和“运行结果语义”，`input_source_meta`、旧提示文案、过渡控制器与超大旧壳文件仍在主路径中起作用；
2. API surface 仍保留通用 artifact 读接口、历史 alias/fallback 读取逻辑和超大 impl 文件，导致新资产接入仍会被当前 A 股产物结构绑住；
3. `backend/scripts` 顶层仍保留大量研究定义型脚本，`study + generated thin script` 虽已建立，但尚未真正成为唯一研究入口；
4. `backend/core` 中多个热点文件仍过大，混合了承载研究主路径的稳定逻辑和可拆分的辅助职责，继续阻碍多资产扩展。

这次 change 的核心约束是：
- 不再以“向后兼容”作为目标；
- 已过时研究入口、历史 alias、过渡提示和兼容壳在不影响 `baseline_V10.1 -> exp_20260314_144548534_7db9` 结果的前提下可以直接删除；
- 所有设计决策都必须优先服务代码优雅性、职责单一、主路径清晰和未来多资产接入。

## Goals / Non-Goals

**Goals:**
- 让桌面前端彻底以 `experiment manifest / runtime snapshot` 为主真相，配置来源只保留为辅助 provenance。
- 删除前端主路径对 fallback 结果面和 `/api/backtest_v2/artifacts/read` 的依赖，结果区只保留 Vue workbench 单 owner。
- 让 `backend/api/backtest_v2` 只暴露 canonical manifest/surface/section/专用接口，不再长期背负历史 alias/fallback 读取。
- 将顶层 `backend/scripts` 中的研究定义型脚本继续迁入 `research/studies/*.study.yaml + backend/scripts/generated/*.py`，并删除过时研究入口。
- 对 `backend/core` 里阻碍结构清晰度的热点文件做职责拆分，但不得改变 `baseline_V10.1` 的执行时点、成交口径和结果。
- 清理前端乱码文案、死分支、残留过渡 helper，使源代码文本和目录结构都恢复整洁状态。

**Non-Goals:**
- 不修改 `baseline_V10.1` 的研究口径、信号时点、执行时点、成交规则和绩效计算方式。
- 不在本 change 中做新的策略优化实验或收益提升尝试。
- 不在本 change 中重写 `breakout_signal_provider.py` 或 `strict_runtime_impl.py` 的核心行为。
- 不保留任何仅为前向兼容而存在、且已妨碍结构清晰度的接口或包装层。

## Decisions

### 1. 以 `baseline_V10.1` 为唯一回归门，不再为历史入口保留主路径兼容
原因：当前系统已经明确 `baseline_V10.1` 是正式主线，继续同时照顾历史入口与历史命名只会让结构债永久存在。以后所有清理的判断标准不是“历史方式还能不能跑”，而是“会不会让 `exp_20260314_144548534_7db9` 的结果漂移”。

备选方案：继续保留旧入口但标记 deprecated。拒绝原因：这会把历史载体继续留在主路径，和本次“最终清债”的目标冲突。

### 2. 前端只保留 `runtime snapshot -> Vue workbench` 一条结果主链
原因：用户已明确要求删除 fallback DOM，并要求前端“只是消费结果”。因此桌面研究页必须固定为：
`desktop-research-page -> fetch manifest/surface/section -> build snapshot -> Vue workbench`
不再允许旧 DOM 面板或旁路面板参与主渲染。

备选方案：保留调试用 fallback 模式。拒绝原因：即使只留调试模式，也会继续迫使 `artifacts.js/backtest_v2.js` 保持双轨逻辑。

### 3. API surface 只保留 canonical contract 和少量专用接口
原因：后续要接入美股 ETF、加密现货和防守层资产，前端不能继续理解当前 A 股 artifact 文件布局。桌面主路径必须只消费：
- manifest
- surface
- surface/{section}
- 少量明确语义的专用接口

`/api/backtest_v2/artifacts/read` 和历史 alias 处理要从主路径退出；如仍需做离线迁移，应放在独立 migration/tooling，而不是运行时常驻。

备选方案：保留 artifact read 作为通用后门。拒绝原因：这会让前端继续知道底层 artifact 细节，直接削弱多资产扩展能力。

### 4. 研究入口强制收口到 `study + generated thin script`
原因：`backend/scripts` 顶层研究脚本是事实上的第二套系统。只要它们继续存在，AI 和人工都会优先在顶层脚本加逻辑，前面的治理规则就会持续失效。本 change 里，已过时或已能映射为 study 的研究脚本默认直接删除，而不是继续保留 wrapper。

备选方案：保留顶层薄 wrapper 方便操作。拒绝原因：用户已明确表示不需要向前兼容，且希望后续以代码优雅性和架构整洁性为最高优先级。

### 5. `backend/core` 只做职责拆分，不改执行语义
原因：`backend/core/AGENTS.md` 明确要求保护执行边界。这里的优雅性债确实存在，但必须通过“拆热点、抽 helper、收边界”的方式解决，而不能顺手改变回测行为。所有 core 层清理都必须经过 `V10.1` 前后对照。

备选方案：趁清理一起改掉内部行为不优雅处。拒绝原因：会直接破坏“清理只以整洁性为目标”的可归因性，也最容易误伤正式锚点结果。

### 6. 先删过渡载体，再统一命名和文本
原因：前端和 API 中仍有乱码文案、历史语义命名、过渡状态字段。处理顺序应是先删除不再需要的历史路径，再对剩余主路径做统一命名、文案和状态语义收口，否则会在已废弃载体上浪费时间。

## Risks / Trade-offs

- [前端来源状态切换造成 UI 行为回归] → 先用静态前端 harness 固定 `config draft`、`source summary`、`membership`、`runtime source` 行为，再删旧状态路径。
- [API 删除 alias/fallback 后历史产物读取失败] → 先运行离线 canonical migration，再将运行时读取收敛为 canonical-only；历史目录如仍不满足要求，直接视为无效旧产物而不是继续扩 runtime。
- [研究脚本直接删除导致人工习惯中断] → 用 `generated thin script` 作为唯一脚本式入口补位，并在 inventory/README 中明确迁移关系。
- [core 热点拆分误伤执行口径] → 只允许抽离纯 helper、类型、展示无关逻辑；每个切片后都复核 `baseline_V10.1` 快照。
- [一次性范围过大导致清理失焦] → 按 5 个收口面推进：API surface、results owner、runtime truth、study entry、core hotspot，并用文件级清单驱动，不做泛化重构。
