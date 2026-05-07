## Why

配置工作区虽然已经做了一轮阶段收口，但现在仍是“旧 `S1-S9 + drawer` 壳上做减法”，还没有真正成为文档里定义的 `config_workspace`。只要主阶段、抽屉职责和高级入口不重新定型，前端就还会持续停留在“旧壳渐进修补”状态。

## What Changes

- 将配置工作区正式收口为少量高价值主阶段与二级高级阶段。
- 定义阶段目录、抽屉说明、阶段职责与高级入口的正式边界。
- 让 `config_workspace` 成为桌面 app 中的正式模块，而不是旧壳 rail/drawer 的别名。
- 继续保留阶段式思路，但重做交互和入口优先级。

## Capabilities

### New Capabilities
- `config-workspace-stage-shell`: 定义新 `config_workspace` 的阶段目录、抽屉边界和主/高级入口。

### Modified Capabilities
- `multi-alpha-workbench-ui`: 配置工作区正式按 `config_workspace` 收口，而不是继续围绕旧壳扩展。
- `frontend-module-split`: 桌面前端模块拆分中，配置工作区拥有自己的正式模块边界。

## Impact

- 影响模块：`frontend/assets/js/desktop-shell/*`、旧 rail/drawer 控制层、配置工作区交互。
- 风险：阶段收得过猛会导致少数高级参数入口难以发现；保留过多则继续信息过载。
