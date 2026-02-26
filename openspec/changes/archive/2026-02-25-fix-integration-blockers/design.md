## Context

系统即将进入端到端通流验证阶段。审计发现：
- 前端 `loadBenchmarkSeries()` 调用 `GET /api/backtest_v2/series/benchmark`，后端无此路由 → 图表 benchmark overlay 静默失败
- `PostgresDataProvider._conn()` 和 `_exec_df()` 无异常处理 → 数据库不可达时原始 psycopg 异常传播到 API 层
- pytest 不在 `requirements.txt` 中 → Docker 内无法执行测试
- 后端 `POST /jobs/{id}/cancel` 已实现，前端无取消按钮 → 长时间运行无法中断

## Goals / Non-Goals

**Goals:**
- 实现 benchmark series API 端点，使前端图表正常叠加基准线
- 在 `pg_provider.py` 连接 / 查询层添加异常处理，返回结构化错误
- 搭建测试基础设施（依赖 + conftest + pytest 配置）
- 前端 pollJob 循环中添加 cancel 按钮

**Non-Goals:**
- 不改造 DataProvider 抽象接口（保持现有 ABC）
- 不添加数据库连接池（当前 per-query 连接模式暂够用）
- 不编写完整的单元测试集（本次只搭框架，完整测试在后续通流脚本变更中）
- 不修改回测引擎核心逻辑

## Decisions

### Decision 1: Benchmark series 端点实现方式

**选择**: 在 `backtest_v2.py` 中新增 `GET /api/backtest_v2/series/benchmark` 路由，复用 `PostgresDataProvider.load_benchmark_daily()` 方法
**备选**: 在前端直接从 artifact 文件读取 → 仅回测完成后可用，首次加载和独立查看时无数据
**理由**: 前端已有 artifact 优先 → API fallback 的逻辑（JS 第 510-529 行），只需实现 API fallback 部分

响应格式（与前端期望匹配）：
```json
{
  "points": [{"date": "2024-01-02", "nav": 1.0}, ...],
  "source": "api"
}
```

NAV 计算：取 benchmark close 列，以第一天 close 为基准归一化（`close / close[0]`）。

### Decision 2: 数据库异常处理策略

**选择**: 在 `_conn()` 中 catch `psycopg.Error`，包装为自定义 `DatabaseConnectionError`；在 `_exec_df()` 中 catch 查询异常，包装为 `DatabaseQueryError`
**备选 A**: 在每个 API handler 中 try/catch → 重复代码多，易遗漏
**备选 B**: FastAPI exception_handler 全局捕获 → 过于宽泛，难以区分数据库错误和其他错误
**理由**: 异常应在发生处包装，带上结构化上下文（table、query_type），API 层只需 catch 自定义异常

异常类定义位置：`backend/core/data/errors.py`（新文件）

### Decision 3: 测试基础设施

**选择**:
- `requirements.txt` 添加 `pytest>=7.4.0`、`pytest-cov>=4.0.0`、`pytest-asyncio>=0.21.0`
- 创建 `tests/conftest.py`，提供 `test_client` fixture（FastAPI TestClient）和 `mock_db_provider` fixture
- 创建 `pytest.ini` 配置 testpaths 和 asyncio_mode
**理由**: 最小可用的测试框架，不过度设计

### Decision 4: Job cancel 按钮位置

**选择**: 在 `pollJob()` 运行期间，将 `wbRunStatus` 旁的运行按钮文本改为 "取消运行"，点击发送 `POST /jobs/{id}/cancel`
**备选**: 在 status panel 中添加 cancel 按钮 → 需要打开面板才能取消，不直观
**理由**: 用户运行回测时视线在 command bar 的 Run 按钮区域，原地变为 Cancel 最自然

## Risks / Trade-offs

- **[风险] benchmark 数据库表为空** → API 端点返回 `{"points": [], "source": "empty"}`，前端已处理空数组场景
- **[风险] 自定义异常引入新依赖** → 保持纯 Python，无额外依赖
- **[权衡] per-query 连接无池化** → 本次不改，留给后续性能优化
- **[权衡] pytest-asyncio 需要 asyncio_mode 配置** → 在 pytest.ini 中设置 `asyncio_mode = auto`
