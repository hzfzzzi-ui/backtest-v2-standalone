## Why

当前桌面端虽然已经有新壳文档和局部实现，但默认入口、主 bootstrap 和结果 snapshot 仍主要被旧壳控制。只要新桌面壳没有正式接管宿主入口，前端就仍然处在“旧壳修补”而不是“新桌面 app”阶段。

## What Changes

- 将桌面端正式宿主入口切到新的单页 `desktop app` host。
- 收口单一 root mount、统一 app state 和统一 API adapter 边界。
- 将旧 `backtest_v2.js`、旧 bridge 和旧桌面 page controls 正式降级为迁移层，并定义退出条件。
- 让结果 snapshot 真正由新桌面 app 持有，而不是长期依赖 bridge。

## Capabilities

### New Capabilities
- `desktop-app-shell-host-cutover`: 定义新桌面壳正式接管宿主入口、挂载边界和迁移退出条件。

### Modified Capabilities
- `frontend-module-split`: 前端模块拆分正式以新桌面壳为根。
- `api-shared-helper-surface`: UI 层正式只经由统一 API adapter，不再沿用旧全局 helper 主路径。
- `results-workbench-snapshot-boundary`: 结果 snapshot 正式由桌面 app state 持有，bridge 仅为迁移工具。

## Impact

- 影响模块：`frontend/index.html`、桌面宿主入口、新桌面壳、旧 `backtest_v2.js`、bridge、共享 API helper。
- 风险：入口切换期间可能破坏加载/hydrate 主链；旧壳退出过早可能影响配置与结果联动。
