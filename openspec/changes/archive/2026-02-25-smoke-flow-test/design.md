## Context

系统有完整的回测 API 链路 (experiment/run_async → jobs → results → benchmark → configs) 但缺乏自动化的端到端验证。目前依赖手工 UI 操作确认联通性。已有 pytest 基础设施 (conftest.py + TestClient)，可直接复用。

## Goals / Non-Goals

**Goals:**
- 一条命令 (`pytest -m smoke`) 验证完整数据流是否联通
- 覆盖 6 条关键路径: DB health → run → poll → artifacts → benchmark → config roundtrip
- 失败时提供清晰的 step 定位 (哪一步断了)
- 复用现有 test_client fixture，不引入新依赖

**Non-Goals:**
- 不测试业务逻辑正确性 (如 Sharpe 计算精度)
- 不测试 cancel 路径 (后续独立加)
- 不 mock 数据库 — 这是真实 DB 的集成测试
- 不覆盖 UI 渲染

## Decisions

### D1: 单文件 6 函数，顺序依赖

测试写在 `tests/test_flow_smoke.py`，6 个 `test_step_N_*` 函数。使用 module-scoped fixture 传递 job_id、run_id 等状态。

**替代方案**: 用 pytest-ordering 或 pytest-dependency 显式声明依赖。
**选择理由**: 函数命名自然排序即可，不引入额外插件。

### D2: module-scoped shared state fixture

用一个 `_flow_state` dict (module scope) 在 steps 之间传递 job_id、run_id、config 等中间产物。每个 step 读写这个 dict。

**替代方案**: 用 class-based test 的 `cls` 属性。
**选择理由**: dict fixture 更简洁，与现有 conftest 风格一致。

### D3: smoke marker 隔离

注册 `@pytest.mark.smoke` marker，默认跑 `pytest` 不会触发这些测试 (需要 `-m smoke`)。在 `pytest.ini` 中添加 `addopts = -m "not smoke"` 排除默认执行。

**替代方案**: 放在独立目录 `tests/smoke/`。
**选择理由**: marker 更灵活，可以和其他 test 共存在 tests/ 下。

### D4: poll 超时 120s + 2s 间隔

实验在 smoke 配置 (3 stocks × 3 months) 下通常 30-60s 完成。120s 超时留足余量。

### D5: 使用内置 smoke config

直接调用 `_flow_script_config_json()` 的等价内容作为请求体，preset 用 `G1-G4`。不依赖磁盘上的 cfg_flow_smoke_v1.json。

## Risks / Trade-offs

- **[真实 DB 依赖]** → 测试只能在有 PostgreSQL 的环境跑。用 marker 隔离，CI 无 DB 时自动跳过。
- **[执行时间长]** → smoke 配置约 30-60s，不适合快速迭代。marker 隔离确保不影响普通 pytest。
- **[数据依赖]** → 需要 DB 中有 2025-01-01~2025-03-31 的 600000.SH/000001.SZ/600519.SH 数据。若数据缺失 step 3 会 fail。
