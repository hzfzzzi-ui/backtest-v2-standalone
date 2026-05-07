# clean-dir-structure Specification

## Purpose

定义仓库主目录与前后端代码目录的目标结构，约束目录迁移后的主路径、过渡路径和遗留路径边界。

## Requirements

### Requirement: Backend 目录统一归集
所有 Python 后端代码 SHALL 位于 `backend/` 目录下。`backend/` SHALL 包含以下子目录：`api/`、`core/`、`configs/`、`scripts/`。

#### Scenario: 回测引擎代码位于 backend/core
- **WHEN** 检查 `backend/core/` 目录
- **THEN** 其子目录结构 SHALL 与当前正式运行链一致，包含数据、信号、组合、执行、审计、工具与 universe 等主模块

#### Scenario: 旧目录已移除
- **WHEN** 检查项目根目录
- **THEN** `backtest_V2/` 目录 SHALL 不存在

### Requirement: Frontend 目录独立清晰
所有前端静态资源 SHALL 位于 `frontend/` 目录下，且 SHALL 不存在嵌套重复的 `assets/assets/` 结构。

#### Scenario: 前端资源扁平化
- **WHEN** 检查 `frontend/assets/` 目录
- **THEN** SHALL 直接包含 `css/`、`js/` 等子目录，不存在重复的 `assets/` 嵌套

#### Scenario: HTML 入口清晰
- **WHEN** 检查 `frontend/` 目录
- **THEN** SHALL 存在 `index.html`
- **THEN** `backtest_v2.html` 这类旧入口 SHALL 不再作为正式入口

### Requirement: Import 路径更新
所有 Python 文件中的 import 路径 SHALL 从旧的 `backtest_V2.backtest_v2.*` 更新到当前 `backend.*` 主路径。

#### Scenario: 无遗留旧 import
- **WHEN** 在整个项目中搜索 `backtest_V2.backtest_v2`
- **THEN** SHALL 返回零结果

#### Scenario: API 路由 import 正确
- **WHEN** 检查 `backend/main.py` 中的 router import
- **THEN** SHALL 使用当前正式 API 路径，而不是旧目录路径

### Requirement: 根目录精简
项目根目录 SHALL 仅包含正式主路径目录：`backend/`、`frontend/`、`research/`、`scripts/`、`tests/`、`docs/`、`outputs/`、`openspec/`、`examples/`，以及必要的根级配置和协作文档，如 `Dockerfile`、`docker-compose.yml`、`package.json`、`package-lock.json`、`pytest.ini`、`vite.results-workbench.config.mjs`、`.gitignore`、`.env`、`AGENTS.md`。

#### Scenario: 架构真相不再停留在根目录文档
- **WHEN** 检查根目录文档入口
- **THEN** 架构真相 SHALL 以 `docs/` 体系为正式入口
- **THEN** 根目录 SHALL NOT 再依赖 `ARCHITECTURE.md` 作为正式架构文档

#### Scenario: 无散落 Python 入口
- **WHEN** 检查项目根目录的 `.py` 文件
- **THEN** SHALL 不存在散落在根目录的 Python 脚本

#### Scenario: 无临时目录
- **WHEN** 检查项目根目录
- **THEN** SHALL 不存在 `tmp/` 目录
- **THEN** SHALL 不存在 `tmp_*` 模式的目录或临时文件

### Requirement: Docker 配置更新
`Dockerfile` 和 `docker-compose.yml` SHALL 反映当前目录结构，确保容器正常构建和运行。

#### Scenario: Dockerfile COPY 路径正确
- **WHEN** 检查 `Dockerfile`
- **THEN** COPY 指令 SHALL 引用 `backend/` 和 `frontend/`，而不是旧目录

#### Scenario: 环境变量更新
- **WHEN** 检查 `docker-compose.yml` 中的环境变量
- **THEN** 与运行根路径相关的变量 SHALL 指向当前正式目录结构

### Requirement: 测试目录结构清晰
测试文件 SHALL 位于 `tests/` 目录下，并按 `unit/`、`integration/`、`frontend/` 分类。

#### Scenario: 测试文件按类型分组
- **WHEN** 检查 `tests/` 目录
- **THEN** SHALL 包含 `unit/`、`integration/` 与 `frontend/` 子目录
