# backend boundary freeze map 2026-03-08

## 目标

把后端公开 API、公开引擎编排、数据库访问、审计写盘四个冻结面定死，后续旧代码清理只能在这些边界之后进行，不允许再把 legacy 字段或 direct DB/provider 逻辑回流到 public surface。

## 冻结面

### 1. Public API surface

唯一公开运行/读取真相：
- `POST /api/backtest_v2/experiment/run`
- `POST /api/backtest_v2/experiment/run_async`
- `POST /api/backtest_v2/execution/preview`
- `POST /api/backtest_v2/artifacts/read`

冻结规则：
- 公开 request model 统一在 [\_public_contracts.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/_public_contracts.py)
- public model `extra=forbid`
- `artifacts/read` 只允许 `exp_id + rel_path`
- `results_dir` 仅允许 internal helper 使用，不再是 public API 输入
- 非 locked candidate 的公开运行只允许 `config_json` 作为配置真相

internal-only 例外：
- [BacktestV2ExperimentRequest](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/_experiment_runner_api.py) 仍可作为内部兼容执行模型存在
- [\_experiment_surface.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/_experiment_surface.py) 仍允许 internal helper 解析 `results_dir`

### 2. Engine pipeline surface

唯一公开编排边界：
- [foundation_shell.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_compat/foundation_shell.py)

冻结规则：
- public single-run orchestrator 只能暴露到 foundation shell
- foundation shell 之后的 `stage pipeline shell -> legacy adapter -> legacy kernel` 全部视为 internal implementation detail
- 不允许新增第二条公开执行路径

internal-only 例外：
- [legacy_adapter.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/adapters/legacy_adapter.py)
- [portfolio_simulator_strict.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/portfolio_simulator_strict.py)

### 3. Database access surface

共享数据库边界：
- [runtime_data_access.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/tools/runtime_data_access.py)
- [data_bundle_builder.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/tools/data_bundle_builder.py)

冻结规则：
- API 的 benchmark/symbol/validate_data/stock_names/industries 统一经 `runtime_data_access.py`
- 主回测路径统一经 `data_bundle_builder.py`
- 不允许在公开路由里直接 `PostgresDataProvider(...)`
- 不允许在公开路由里重新拼 universe resolve/filter 流程

internal-only 例外：
- `validate_pg.py` 仍直接消费 PG 连接参数，但由 boundary module 负责喂入 symbol 集和口径

### 4. Audit surface

共享审计契约：
- [experiment_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/experiment_audit.py)

冻结规则：
- `stage_summary`
- `stage_pipeline`
- `audit.json`

以上三者必须走共享 contract helper，禁止 foundation shell 与 artifact stabilize 各自拼一份 audit 口径。

internal-only 例外：
- report 导出可继续读取 `audit.json/run_meta/manifest`，但不再拥有独立 audit 真相

## 后续清理门槛

满足以下条件后，才允许继续做更激进的 legacy retirement：
- 锁定基线 `exp_20260308_021045840_cde0` 的核心 compare 继续 `PASS`
- public request model 不再接受 legacy surface 字段
- API 路由不再直接 new provider
- 审计 contract 不再分散在 foundation shell 与 stabilize 两处
