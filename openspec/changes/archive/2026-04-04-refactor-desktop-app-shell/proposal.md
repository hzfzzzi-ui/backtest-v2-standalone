## Why

当前桌面前端仍是三层叠加：

- 静态宿主 + 旧桌面壳
- bridge/页面控制层
- `results-workbench` 结果子应用

而正式前端文档已经收口：

- 桌面端应为新的单页 desktop app
- `results-workbench` 只应是 `results_workspace` 子模块
- 桌面端应采用单一顶层 app state
- 旧壳、旧 bridge、旧状态切片与旧控制模块都应视为过渡层并最终删除

如果不单独起 change 收口前端新壳，旧前端会继续以 bridge 和旧页面控制模块为中心长大。

## What Changes

- 新增 `desktop-app-shell` 正式能力，定义新的单页 desktop app 宿主。
- 将 `frontend-module-split`、`multi-alpha-workbench-ui`、`results-workbench-finalization`、`api-shared-helper-surface` 收口到新桌面架构。
- 明确 `backtest_v2.js`、`ui-controls.js`、`artifacts.js`、`results-workbench-bridge.js`、`desktop-*.js` 全部是过渡层。
- 固定桌面/移动端共享边界：共享 API adapter 与合同，不共享壳层 UI。

## Capabilities

### New Capabilities
- `desktop-app-shell`: 定义正式桌面单页应用、顶层模块、单一 app state 与统一宿主边界。

### Modified Capabilities
- `frontend-module-split`: 前端模块划分以新 desktop app 为中心，而不是继续围绕旧壳和结果子应用。
- `multi-alpha-workbench-ui`: 配置工作区保留阶段式思路，但正式归于 `config_workspace`。
- `results-workbench-finalization`: `results-workbench` 降级为 `results_workspace` 子模块，而不是整页壳。
- `api-shared-helper-surface`: UI 层禁止直接 `fetch`，统一通过共享 API adapter / data service。

## Impact

- 主要影响模块：
  - `frontend/index.html`
  - `frontend/app/results-workbench`
  - `frontend/assets/js/pages/desktop-*`
  - `frontend/assets/js/state/*`
  - `frontend/assets/js/api*.js`
- 主要风险：
  - 旧壳与新桌面 app 并存时容易产生双重真相
  - bridge 清理过早会打断结果加载
- 主要验证：
  - 桌面主工作流回归
  - 结果加载与配置加载性能回归
  - 移动端口径一致性回归
