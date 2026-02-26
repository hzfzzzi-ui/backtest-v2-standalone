## Why

当前项目目录存在多个问题：`backtest_V2/backtest_v2/` 嵌套命名冗余，`frontend/assets/assets/` 双层重复，根目录散落配置文件与入口混杂，前后端边界模糊。需要一次性梳理为清晰的前后端分离结构，降低新人上手成本，简化 Docker 构建和部署路径。

## What Changes

- **BREAKING**: 将 `backtest_V2/backtest_v2/` 扁平化为 `backend/core/`，消除冗余嵌套
- **BREAKING**: 将 `backtest_V2/configs/` 移动到 `backend/configs/`
- **BREAKING**: 将 `backend/api/` 提升为 `backend/api/`（保持原位，但归入统一 backend 结构）
- 将 `main.py` 移入 `backend/main.py`，根目录保留薄启动脚本或直接通过 uvicorn 启动
- 消除 `frontend/assets/assets/` 双层嵌套，统一为 `frontend/assets/`
- 将 `scripts/` 归入 `backend/scripts/`
- 将 `tests/` 拆分归入各自模块，或保持顶层但结构化为 `tests/backend/` 和 `tests/integration/`
- 更新 `Dockerfile`、`docker-compose.yml` 以匹配新路径
- 输出 `ARCHITECTURE.md` 架构文档

## Capabilities

### New Capabilities
- `clean-dir-structure`: 项目目录扁平化与前后端分离重组
- `architecture-doc`: 输出清晰的架构文档 (ARCHITECTURE.md)

### Modified Capabilities

（无现有 spec 需修改）

## Impact

- **代码路径**: 所有 Python import 路径需更新（`backtest_V2.backtest_v2.*` → `backend.core.*`）
- **前端静态资源**: HTML 中的资源引用路径需更新
- **Docker**: `Dockerfile` COPY 指令和 `docker-compose.yml` volume 映射需更新
- **CI/测试**: 测试文件 import 路径需同步更新
- **入口**: `main.py` 中的路径常量和 router import 需更新
