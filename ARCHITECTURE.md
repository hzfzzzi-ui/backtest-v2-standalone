# Architecture

## 项目结构

```
backtest_V2_standalone/
├── backend/                         # 所有后端 Python 代码
│   ├── main.py                      # FastAPI 应用入口
│   ├── requirements.txt             # Python 依赖
│   ├── api/                         # API 层
│   │   └── endpoints/
│   │       ├── backtest_v2.py       # 主路由（回测运行、实验、配置管理）
│   │       └── backtest_v2_artifacts.py  # 产物读取与稳定化
│   ├── core/                        # 回测引擎核心
│   │   ├── analytics/               # 分析报告、权益曲线、交易统计
│   │   ├── buses/                   # 实验总线、可观测性
│   │   ├── cli/                     # 命令行入口
│   │   ├── config/                  # 配置模型与加载
│   │   ├── core/                    # 核心模型、调度器、类型定义
│   │   ├── data/                    # 数据提供者（PG、内存、快照）
│   │   ├── engine_vector/           # 向量化回测引擎
│   │   ├── execution/               # 执行层（撮合、成本、去重、约束）
│   │   ├── portfolio/               # 组合管理（账户、持仓、下单、快照）
│   │   ├── strategies/              # 策略库（SMA、ATR、多因子等）
│   │   ├── tools/                   # 工具（实验运行器、bundle、验证）
│   │   └── universe/                # 股票池定义
│   ├── configs/                     # 策略配置文件 (JSON/CSV)
│   └── scripts/                     # 工具脚本
├── frontend/                        # 前端静态资源
│   ├── index.html                   # 单页应用入口
│   └── assets/
│       ├── css/                     # 样式文件
│       ├── js/                      # JavaScript 模块
│       └── images/                  # 图片资源
├── tests/                           # 测试
│   ├── unit/                        # 单元测试
│   └── integration/                 # 集成测试
├── docs/                            # 项目文档
├── outputs/                         # 运行时产出（回测结果、报告）
├── Dockerfile                       # Docker 镜像构建
├── docker-compose.yml               # 容器编排
└── package.json                     # 项目元信息
```

## 模块职责

### backend/api/

FastAPI 路由层，负责：
- 接收前端请求，校验参数
- 调用 core 引擎执行回测/实验
- 管理异步任务（Job 队列）
- 读取和返回回测产物

### backend/core/

回测引擎核心，各子模块职责：

| 模块 | 职责 |
|------|------|
| `analytics/` | 回测结果分析：权益曲线、交易 PnL、集中度、报告导出 |
| `buses/` | 实验总线（批量运行、变体生成）和可观测性（日志、指标、可复现性） |
| `config/` | 配置模型定义、JSON 加载与校验 |
| `core/` | 核心数据模型（DailySnapshot 等）、调度器、类型枚举 |
| `data/` | 数据层抽象：PostgreSQL 提供者、内存提供者、数据快照 |
| `engine_vector/` | 向量化回测引擎：信号矩阵、特征计算、组合模拟 |
| `execution/` | 执行层：L1 撮合、涨跌停检测、交易成本、中国市场约束 |
| `portfolio/` | 组合管理：账户余额、持仓追踪、下单构建、头寸调整 |
| `strategies/` | 策略实现：SMA 交叉、ATR 止损、多因子、动量等 |
| `tools/` | 高层工具：实验运行器、bundle 执行、验证扫描 |
| `universe/` | 股票池定义（沪深 300、中证 500） |

### backend/configs/

策略配置文件，JSON 格式定义回测参数（标的、时间范围、策略参数等）。

### frontend/

纯静态单页应用（无构建工具链），通过 FastAPI 的 StaticFiles 中间件提供服务。

## 前后端交互

前端通过 REST API 与后端交互：

```
┌──────────────┐     HTTP/JSON      ┌──────────────┐
│   Frontend   │ ──────────────────▶ │   Backend    │
│  (静态 HTML/ │                     │  (FastAPI)   │
│   JS/CSS)    │ ◀────────────────── │              │
└──────────────┘                     └──────┬───────┘
                                            │
                                     ┌──────▼───────┐
                                     │  Core Engine  │
                                     │  (回测引擎)   │
                                     └──────┬───────┘
                                            │
                                     ┌──────▼───────┐
                                     │  PostgreSQL   │
                                     │  (行情数据)   │
                                     └──────────────┘
```

### 主要 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/backtest_v2/validate_data` | GET | 数据验证 |
| `/api/backtest_v2/run_async` | POST | 异步运行回测 |
| `/api/backtest_v2/experiment/run_async` | POST | 异步运行实验 |
| `/api/backtest_v2/jobs/{job_id}` | GET | 查询任务状态 |
| `/api/backtest_v2/jobs/{job_id}/cancel` | POST | 取消任务 |
| `/api/backtest_v2/results/{run_id}` | GET | 获取回测结果 |
| `/api/backtest_v2/configs` | GET/POST | 配置管理 |
| `/api/backtest_v2/execution/preview` | POST | 执行预览 |
| `/api/backtest_v2/artifacts/read` | POST | 读取产物文件 |

## 启动方式

### 本地开发

```bash
# 安装依赖
pip install -r backend/requirements.txt

# 启动服务（从项目根目录执行）
uvicorn backend.main:app --reload --port 8000

# 访问 http://localhost:8000
```

### Docker 部署

```bash
# 构建并启动
docker compose up -d

# 访问 http://localhost:8091
```

环境变量：
- `BACKTEST_V2_ROOT`: 回测引擎根目录（容器内默认 `/app/backend/core`）
- `RESULTS_ROOT`: 结果输出目录（默认 `outputs`）
- `PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD`: PostgreSQL 连接参数
