## Why

当前桌面前端的主启动权仍由 `frontend/assets/js/backtest_v2.js` 持有，`index.html` 直接调用它暴露的 `init()`，共享 `state` 也由它在脚本加载期创建。这使 `desktop-shell/*` 已经落地的 owner 边界无法真正闭环，也让旧壳继续承担主链职责，阻塞后续把 legacy 壳收缩为兼容层。

## What Changes

- 引入正式的 desktop host/bootstrap owner，接管共享 `state` 初始化与页面启动分发。
- 调整 `index.html` 的 script 装载顺序与启动入口，使主启动不再直接依赖 `backtest_v2.js` 暴露的 `init()`。
- 将 `backtest_v2.js` 降级为 compat shell：允许继续提供过渡 helper 与桥接逻辑，但不再拥有主 bootstrap owner 身份。
- 同步前端 harness，使测试主路径与页面真实装载链保持一致。
- 补充前端 owner cutover 的边界说明与任务拆分，确保后续还能继续把 helper/runtime 依赖从旧壳迁出。

## Capabilities

### New Capabilities
- 无

### Modified Capabilities
- `desktop-app-shell-host-cutover`: 明确 desktop host 接管默认宿主入口、共享状态初始化与主启动分发，旧壳退出主 bootstrap owner 身份。
- `frontend-module-split`: 更新前端主装载链与模块 owner 边界，要求 `index.html` 与前端 harness 优先走正式 host/bootstrap owner。

## Impact

- 影响前端主入口：`frontend/index.html`
- 影响桌面宿主层：`frontend/assets/js/desktop-shell/*`
- 影响旧壳：`frontend/assets/js/backtest_v2.js`
- 影响前端测试基建：`tests/frontend/multi_alpha_workbench_harness.cjs`
- 不改变研究口径、运行合同与回测结果目标版本；本次只调整前端宿主 owner 与装载边界
