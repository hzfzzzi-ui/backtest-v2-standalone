## Why

当前系统虽然已经完成了 API 边界、执行总线和研究命令面的主干重构，但仍保留几块影响长期演进的结构性遗留：前端主路径仍混用 `artifacts/read` 和 fallback 结果 DOM，配置真相仍偏 `config_id` 驱动，研究入口治理也尚未彻底收口。现在需要在不改变 `baseline_V10_1 -> exp_20260314_144548534_7db9` 回归结果的前提下，继续把主路径收敛到更适合多资产扩展的结构。

## What Changes

- 收口桌面主路径 API surface：前端主路径尽量废弃 `/api/backtest_v2/artifacts/read`，改为只消费 `manifest / surface / surface/{section}` 与少量专用接口。
- 完成结果工作台单 owner 化：移除生产主路径中的 fallback 结果 DOM，仅保留 Vue workbench 作为唯一结果渲染 owner。
- 从前端旧控制器中抽离配置核心：把 `ui-controls.js` 中“表单 -> config draft -> runtime request”的核心配置构建逻辑拆出，旧文件继续退化为薄壳。
- 统一前端运行真相：桌面研究页以 `experiment manifest / runtime snapshot` 为真相，配置仅作为输入来源之一，而不是页面的长期主语义。
- 继续收口研究入口：默认只允许 `study + generated thin script` 作为正式实验入口，高频实验不再回流到顶层大型研究脚本。

## Capabilities

### New Capabilities
- `<none>`: 本次变更不新增独立 capability，而是在既有能力上继续收口主路径。

### Modified Capabilities
- `http-surface-boundary-split`: 调整桌面主路径的读取方式，要求主路径优先消费 `manifest / surface / section`，弱化通用 `artifacts/read`。
- `runtime-boundary-contracts`: 强化桌面页壳以 `experiment manifest / runtime snapshot` 为真相的约束，降低 `config_id` 驱动语义。
- `frontend-module-split`: 继续拆分 `ui-controls.js`、`backtest_v2.js`、`artifacts.js`，将配置核心与结果消费逻辑外提。
- `results-workbench-finalization`: 从“fallback 受控存在”推进到“生产主路径只保留 Vue workbench 结果 owner”。
- `script-surface-governance`: 将正式实验入口进一步收口到 `study + generated thin script`，减少顶层脚本回流。

## Impact

- Affected code:
  - `frontend/assets/js/backtest_v2.js`
  - `frontend/assets/js/ui-controls.js`
  - `frontend/assets/js/artifacts.js`
  - `frontend/assets/js/pages/*`
  - `frontend/app/results-workbench/*`
  - `backend/api/backtest_v2/*`
  - `backend/research/*`
  - `backend/scripts/*`
- Affected APIs:
  - 桌面端主路径 artifact 读取方式
  - `surface / surface/{section}` 的职责边界
- Affected systems:
  - 结果工作台渲染 ownership
  - 前端配置草稿编译路径
  - 研究入口治理与生成脚本路径
- Regression gate:
  - 全程以前后对照 `baseline_V10_1 -> exp_20260314_144548534_7db9` 为门槛，确认 `perf / orders / trades / nav` 不漂移。
