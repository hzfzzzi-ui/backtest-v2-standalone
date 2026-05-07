## Why

虽然桌面端主 bootstrap owner 已经切到 host，但前端主链仍大量依赖 `backtest_v2.js` 暴露的基础 helper 与 runtime surface，包括 `state` 词法绑定、DOM helper、资产范围 helper、loaded source/runtime source 维护和 results workbench bridge helper。这使旧壳虽然失去了主启动权，却仍是其他模块事实上的 shared runtime owner，后续无法真正退出主装载链。

## What Changes

- 新增正式的 `desktop-shell/runtime-surface.js`，承接当前跨文件复用的前端 runtime surface。
- 将 `state` 词法绑定、基础 DOM/helper、asset scope helper、loaded/runtime source helper 和 results workbench bridge helper 从 `backtest_v2.js` 迁出。
- 调整 `index.html` 与前端 harness，确保 `runtime-surface.js` 在依赖它的脚本之前加载。
- 将 `backtest_v2.js` 进一步收缩为 compat shell，不再承载跨模块 shared runtime surface。

## Capabilities

### New Capabilities
- 无

### Modified Capabilities
- `frontend-module-split`: 要求前端跨模块共享 helper/runtime surface 由正式模块承接，不再挂在 `backtest_v2.js`。
- `desktop-app-shell-host-cutover`: 要求 host cutover 之后，旧壳不得继续作为 shared runtime owner。

## Impact

- 影响前端主链：`frontend/index.html`
- 影响正式桌面宿主层：`frontend/assets/js/desktop-shell/*`
- 影响 compat shell：`frontend/assets/js/backtest_v2.js`
- 影响前端测试基建：`tests/frontend/multi_alpha_workbench_harness.cjs`
- 不改变研究口径、回测合同与目标结果版本；本次只进一步收缩旧壳 runtime 依赖面
