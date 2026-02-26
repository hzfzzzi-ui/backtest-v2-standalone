## Context

当前项目结构：

```
backtest_V2_standalone/
├── main.py                          # FastAPI 入口
├── backend/api/endpoints/           # 2 个 API 路由文件
├── backtest_V2/backtest_v2/         # 核心回测引擎（冗余嵌套）
├── backtest_V2/configs/             # 策略配置 JSON
├── frontend/
│   ├── backtest_v2.html
│   └── assets/assets/               # 双层嵌套静态资源
├── scripts/
├── tests/
├── docs/
├── outputs/                         # 运行结果（运行时生成）
├── Dockerfile
├── docker-compose.yml
└── package.json                     # 仅含项目元信息，无实际前端构建
```

核心问题：
1. `backtest_V2/backtest_v2/` 双层命名冗余，import 路径冗长
2. `frontend/assets/assets/` 双层嵌套，且两层内容完全重复
3. 根目录 `main.py` 职责不清，backend 入口散落在外
4. `scripts/`、`tests/` 与 backend 的归属关系不明确

## Goals / Non-Goals

**Goals:**
- 消除所有冗余嵌套层级
- 前后端目录完全分离，职责清晰
- 所有 Python 代码归入 `backend/`，所有静态资源归入 `frontend/`
- import 路径简短直观
- Docker 构建路径简洁
- 输出 ARCHITECTURE.md 架构文档

**Non-Goals:**
- 不引入前端构建工具链（保持纯静态 HTML/JS/CSS）
- 不重构 Python 代码逻辑，仅调整文件位置和 import 路径
- 不改变 API 接口行为
- 不迁移数据库或修改数据模型

## Decisions

### D1: 目标目录结构

```
backtest_V2_standalone/
├── backend/
│   ├── main.py                      # FastAPI 入口（从根目录移入）
│   ├── api/
│   │   └── endpoints/
│   │       ├── backtest_v2.py
│   │       └── backtest_v2_artifacts.py
│   ├── core/                        # 从 backtest_V2/backtest_v2/ 扁平化
│   │   ├── analytics/
│   │   ├── buses/
│   │   ├── cli/
│   │   ├── config/
│   │   ├── core/
│   │   ├── data/
│   │   ├── engine_vector/
│   │   ├── execution/
│   │   ├── portfolio/
│   │   ├── strategies/
│   │   ├── tools/
│   │   └── universe/
│   ├── configs/                     # 从 backtest_V2/configs/ 移入
│   ├── scripts/                     # 从根 scripts/ 移入
│   └── requirements.txt             # 从 backend/api/ 提升
├── frontend/
│   ├── index.html                   # 重命名 backtest_v2.html
│   └── assets/
│       ├── css/
│       ├── js/
│       └── images/
├── tests/
│   ├── unit/                        # 从 backtest_V2/backtest_v2/tests/ 迁入
│   └── integration/                 # 从根 tests/ 迁入
├── docs/
├── outputs/                         # 运行时产出（gitignore）
├── Dockerfile
├── docker-compose.yml
├── ARCHITECTURE.md
└── README.md
```

**Rationale**: 消除 `backtest_V2/backtest_v2/` 和 `frontend/assets/assets/` 两处冗余嵌套。所有 Python 代码（引擎 + API + 脚本 + 配置）统一在 `backend/` 下，所有静态资源在 `frontend/` 下。根目录仅保留部署配置和文档。

### D2: Import 路径迁移策略

| 旧路径 | 新路径 |
|--------|--------|
| `backtest_V2.backtest_v2.analytics.*` | `backend.core.analytics.*` |
| `backtest_V2.backtest_v2.core.*` | `backend.core.core.*` |
| `backtest_V2.backtest_v2.strategies.*` | `backend.core.strategies.*` |
| `backend.api.endpoints.*` | `backend.api.endpoints.*`（不变） |

**Rationale**: 使用全局搜索替换，一次性完成。`backend.core.core` 虽有 `core` 重复，但语义清晰（`backend.core` 是引擎模块，`core.core` 是引擎核心子模块），且避免了对引擎内部结构的进一步重命名。

### D3: 前端资源去重

当前 `frontend/assets/` 和 `frontend/assets/assets/` 内容完全重复。保留内层内容，移至 `frontend/assets/`。HTML 中的引用路径从 `/assets/assets/...` 改为 `/assets/...`。

**Rationale**: `main.py` 已优先挂载内层目录，说明内层是实际使用版本。

### D4: 根目录入口处理

移除根目录 `main.py`，改为 `backend/main.py`。启动命令从 `uvicorn main:app` 改为 `uvicorn backend.main:app`。

`package.json` 保留在根目录（仅元信息，无构建需求）。

### D5: 移除 tmp_ 目录

`tmp_atr_card08/`、`tmp_candidate_demo/`、`tmp_reason_taxonomy/` 为临时实验数据，加入 `.gitignore` 或直接删除。

## Risks / Trade-offs

- **[Import 路径全量替换]** → 使用 IDE 全局替换 + grep 验证，每次替换后运行测试确认
- **[Docker 构建中断]** → Dockerfile 和 docker-compose.yml 必须同步更新，最后统一验证
- **[环境变量 BACKTEST_V2_ROOT]** → 需更新为指向新路径 `backend/core`，或移除此环境变量改用相对路径
- **[第三方引用]** → 如有外部系统通过旧路径引用，需通知相关方。当前为独立项目，风险低
