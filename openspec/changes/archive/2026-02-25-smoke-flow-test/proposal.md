## Why

系统缺少一个可重复执行的端到端通流验证。当前只能手工在 UI 上点击运行来确认各环节是否联通。需要一个 pytest 级的 smoke flow test，部署后一条命令验证 DB 连接、回测执行、产物输出、基准线叠加、配置往返等全链路是否正常。

## What Changes

- 新增 `tests/test_flow_smoke.py`：6 步顺序测试覆盖完整数据流
  - Step 1: DB health check (benchmark API 验证 DB 可达)
  - Step 2: Launch experiment (POST run_async)
  - Step 3: Poll to success (轮询 job 状态)
  - Step 4: Verify artifacts (产物完整性 + 结构校验)
  - Step 5: Benchmark overlay (基准线归一化校验)
  - Step 6: Config roundtrip (保存 → 加载 deep equal)
- 新增 pytest marker `smoke` 用于独立运行此类测试
- 复用现有 `conftest.py` 的 `test_client` fixture (TestClient + 真实 DB)

## Capabilities

### New Capabilities
- `smoke-flow-test`: 端到端通流测试，覆盖 experiment 执行链路、产物校验、基准线 API、配置 roundtrip

### Modified Capabilities

(无)

## Impact

- 新增文件: `tests/test_flow_smoke.py`
- 修改文件: `pytest.ini` (添加 smoke marker 注册)
- 依赖: 真实 PostgreSQL 连接 + `configs/pams_cn_pg.json` 存在
- 不影响生产代码，仅测试层
