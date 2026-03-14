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
- 手机看板：`http://<私网 IP>:8091/mobile`

### 本地开发

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

访问：`http://localhost:8000/`

## 手机看板

手机端使用独立的 `/mobile` 入口，不影响现有电脑端研究平台。默认情况下，手机看板只允许以下 Host 访问：

- `localhost` / `127.0.0.1` / `::1`
- 局域网私有 IP（RFC1918）
- `100.64.0.0/10` 这类私有 overlay 网络地址
- `MOBILE_ALLOWED_HOSTS` 显式白名单中的主机

建议只在可信局域网或私有网络中通过 HTTP 使用，不要将 `/mobile` 或 `/api/mobile/*` 暴露到公网域名或公网 IP。

### 手机看板环境变量

- `MOBILE_DASHBOARD_PASSWORD`：手机看板登录口令，必填
- `MOBILE_AUTH_SECRET`：签名 session cookie 的密钥，必填
- `MOBILE_SESSION_TTL_SECONDS`：登录会话有效期，默认 `43200`
- `MOBILE_PRIVATE_ACCESS_ENABLED`：是否启用私网 Host 限制，默认 `true`
- `MOBILE_ALLOWED_HOSTS`：逗号分隔的额外允许主机名单

### 手机看板数据来源

手机看板后端会聚合以下产物：

- `outputs/experiments/index.json` 用于选择最新实验
- 单个实验目录中的 `manifest.json`、`perf.json`、`portfolio_daily.csv`、`portfolio_trades.csv`
- `outputs/market_snapshots/<trade_date>/market_snapshot.json`
- 基于该实验配置调用 `/api/backtest_v2/execution/preview` 生成的下一次执行预览

因此手机看板上的“建议买入 / 卖出”是面向下一次执行的指引，不是已经成交的事实。

## 说明

- 本服务默认连接现有 `pams-postgres`（通过外部网络 `pams_default`）。
- 若要连接其它数据库，修改 `docker-compose.yml` 中 PG 环境变量。
- 回测产物写入：`./outputs`（可通过 `RESULTS_ROOT` 覆盖）。
