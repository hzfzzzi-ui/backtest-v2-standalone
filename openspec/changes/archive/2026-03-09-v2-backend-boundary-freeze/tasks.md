## 1. Public API Freeze

- [x] 1.1 新建严格 public contract 模块，并让 `/api/backtest_v2/experiment/run`、`/run_async`、`/execution/preview`、`/artifacts/read` 改为只接收冻结字段；DoD: public model `extra=forbid`，`artifacts/read` 不再接受 `results_dir`；验证: 定向 harness + 前端 payload smoke；风险: 前端仍发送 legacy 字段导致 422
- [x] 1.2 同步前端 artifact/run/preview payload，只保留公开契约要求的字段；DoD: `artifacts.js` 不再发送 `results_dir`，run payload 不再发送 legacy config 字段；验证: 静态 grep + 定向 harness；风险: UI 仍有隐藏入口依赖旧字段

## 2. Database Boundary Freeze

- [x] 2.1 新建共享数据库边界模块，统一 runtime config/provider 创建与 benchmark/symbol 序列读取；DoD: `backtest_v2.py` benchmark/symbol 路由不再直接 `PostgresDataProvider(...)`；验证: 直调 harness；风险: provider 初始化参数漂移
- [x] 2.2 把 `validate_data` 的 runtime universe 解析与预过滤逻辑迁入数据库边界模块；DoD: `backtest_v2.py` 不再直接调用 `resolve_universe_by_mode/apply_universe_filters/build_candidates_from_ohlcv`；验证: 定向 harness；风险: universe/filter 口径漂移
- [x] 2.3 把公开产物稳定化阶段需要的 stock name / ST 辅助 DB 查询迁入同一边界模块；DoD: `backtest_v2_artifacts.py` 不再内嵌 direct psycopg 查询函数；验证: 定向 harness；风险: 产物辅助字段缺失

## 3. Pipeline & Audit Freeze

- [x] 3.1 新建共享 audit contract 模块，统一 `stage_summary`、`stage_pipeline`、`audit.json` 归一化；DoD: foundation shell 与 artifact stabilize 共用同一 audit helper；验证: 定向 harness；风险: manifest/run_meta/audit 字段漂移
- [x] 3.2 补 boundary freeze 文档，写清 public API、foundation shell、db boundary、audit contract 的唯一职责与 internal-only 例外；DoD: 形成可引用的 freeze map；验证: 文档审阅；风险: 边界描述模糊导致后续继续越界开发

## 4. Guardrails

- [x] 4.1 补 targeted tests，覆盖 strict public contract、manifest-only artifact read、shared db boundary、shared audit contract；DoD: 新测试能阻止旧表面回流；验证: direct harness；风险: 只测到 happy path
- [x] 4.2 运行 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`，确认锁定基线 `exp_20260308_021045840_cde0` 的核心产物继续 `PASS`；DoD: 仅允许 `report.html` 保持诊断性 `WARN`；验证: baseline compare 报告；风险: seemingly harmless boundary cleanup 误伤产物链路
