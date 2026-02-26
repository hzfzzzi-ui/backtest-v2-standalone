## Why

系统即将编写最小通流脚本验证前后端数据库联调，但审计发现 3 个阻塞项阻止端到端通流：
1. 前端 benchmark 图表叠加调用 `/api/backtest_v2/series/benchmark`，后端无此端点（静默失败）
2. `PostgresDataProvider._conn()` 无异常处理，数据库不可达时原始异常崩溃
3. pytest 未在 `requirements.txt` 中，测试无法在 Docker 内执行

## What Changes

- 新增 `/api/backtest_v2/series/benchmark` GET 端点：从 `pit_index_daily` 查询指数日线，返回 `{points: [{date, nav}], source}` 格式
- `pg_provider.py::_conn()` 和 `_exec_df()` 添加连接 / 查询异常处理，统一返回可理解的错误信息
- `backend/requirements.txt` 添加 pytest + pytest-cov + pytest-asyncio
- 创建 `tests/conftest.py` 共享 fixture（FastAPI TestClient、mock DB provider）
- 前端 job cancel 按钮（后端 `/jobs/{id}/cancel` 已实现，前端无 UI 触发）

## Capabilities

### New Capabilities
- `benchmark-series-api`: 后端 benchmark 时间序列查询端点，供前端图表叠加使用
- `db-connection-resilience`: 数据库连接和查询的异常处理与优雅降级
- `test-infrastructure`: pytest 依赖、conftest.py fixture、Docker 内测试能力
- `job-cancel-ui`: 前端回测任务取消按钮

### Modified Capabilities

## Impact

- **后端 API**: 新增 1 个 GET 端点；修改 `pg_provider.py` 连接层
- **前端**: 添加 cancel 按钮到 status panel 或 command bar
- **依赖**: `requirements.txt` 新增 3 个 test 依赖
- **测试**: 新建 `conftest.py`；现有 7 个测试不受影响
- **Docker**: Dockerfile 无需改动（test 依赖随 requirements.txt 安装）
