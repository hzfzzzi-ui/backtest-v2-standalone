# backtest_V2_standalone

独立回测系统打包（前后端分离 + 数据库接口 + 测试 + 文档）。

## 目录结构

- `backend/main.py`：FastAPI 应用入口
- `backend/api/endpoints/`：API 路由（回测接口 + 产物协议）
- `backend/core/`：回测引擎核心模块
- `backend/configs/`：策略配置文件
- `backend/scripts/`：工具脚本
- `frontend/index.html` + `frontend/assets/`：前端控制台
- `tests/unit/` + `tests/integration/`：测试
- `docs/`：架构与 schema 文档

详细架构说明参见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 启动

### Docker 部署

```bash
docker compose up -d --build
```

访问：
- 前端：`http://localhost:8091/`
- 健康检查：`http://localhost:8091/healthz`

### 本地开发

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

访问：`http://localhost:8000/`

## 说明

- 本服务默认连接现有 `pams-postgres`（通过外部网络 `pams_default`）。
- 若要连接其它数据库，修改 `docker-compose.yml` 中 PG 环境变量。
- 回测产物写入：`./outputs`（可通过 `RESULTS_ROOT` 覆盖）。
