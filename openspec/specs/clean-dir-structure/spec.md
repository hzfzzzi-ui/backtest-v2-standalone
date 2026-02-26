## ADDED Requirements

### Requirement: Backend 目录统一归集
所有 Python 后端代码 SHALL 位于 `backend/` 目录下。`backend/` SHALL 包含以下子目录：`api/`（API 路由）、`core/`（回测引擎）、`configs/`（策略配置）、`scripts/`（工具脚本）。

#### Scenario: 回测引擎代码位于 backend/core
- **WHEN** 检查 `backend/core/` 目录
- **THEN** 其子目录结构 SHALL 与原 `backtest_V2/backtest_v2/` 一致（analytics, buses, cli, config, core, data, engine_vector, execution, portfolio, strategies, tools, universe）

#### Scenario: 旧目录已移除
- **WHEN** 检查项目根目录
- **THEN** `backtest_V2/` 目录 SHALL 不存在

### Requirement: Frontend 目录独立清晰
所有前端静态资源 SHALL 位于 `frontend/` 目录下，且 SHALL 不存在嵌套重复的 `assets/assets/` 结构。

#### Scenario: 前端资源扁平化
- **WHEN** 检查 `frontend/assets/` 目录
- **THEN** SHALL 直接包含 `css/`、`js/` 子目录，不存在 `assets/` 子目录

#### Scenario: HTML 入口重命名
- **WHEN** 检查 `frontend/` 目录
- **THEN** SHALL 存在 `index.html` 文件，不存在 `backtest_v2.html`

### Requirement: Import 路径更新
所有 Python 文件中的 import 路径 SHALL 从 `backtest_V2.backtest_v2.*` 更新为 `backend.core.*`。

#### Scenario: 无遗留旧 import
- **WHEN** 在整个项目中搜索 `backtest_V2.backtest_v2`
- **THEN** SHALL 返回零结果

#### Scenario: API 路由 import 正确
- **WHEN** 检查 `backend/main.py` 中的 router import
- **THEN** SHALL 使用 `from backend.api.endpoints.backtest_v2 import router`

### Requirement: 根目录精简
项目根目录 SHALL 仅包含：`backend/`、`frontend/`、`tests/`、`docs/`、`outputs/`、`openspec/`、配置文件（Dockerfile, docker-compose.yml, package.json, .env）和文档（README.md, ARCHITECTURE.md）。

#### Scenario: 无散落 Python 入口
- **WHEN** 检查项目根目录的 `.py` 文件
- **THEN** SHALL 不存在任何 `.py` 文件

#### Scenario: 无临时目录
- **WHEN** 检查项目根目录
- **THEN** SHALL 不存在 `tmp_*` 模式的目录

### Requirement: Docker 配置更新
Dockerfile 和 docker-compose.yml SHALL 反映新目录结构，确保容器正常构建和运行。

#### Scenario: Dockerfile COPY 路径正确
- **WHEN** 检查 Dockerfile
- **THEN** COPY 指令 SHALL 引用 `backend/` 和 `frontend/` 而非旧路径

#### Scenario: 环境变量更新
- **WHEN** 检查 docker-compose.yml 中的环境变量
- **THEN** `BACKTEST_V2_ROOT` SHALL 指向 `/app/backend/core`

### Requirement: 测试目录结构化
测试文件 SHALL 位于 `tests/` 目录下，按 `unit/` 和 `integration/` 分类。

#### Scenario: 测试文件按类型分组
- **WHEN** 检查 `tests/` 目录
- **THEN** SHALL 包含 `unit/` 和 `integration/` 子目录
