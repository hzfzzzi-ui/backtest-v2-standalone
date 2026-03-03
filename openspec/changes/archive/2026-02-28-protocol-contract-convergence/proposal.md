## Why

当前回测协议在文件命名与字段命名上存在漂移（例如 `reason_codes.csv` 与 `reason_code_counts.csv` 并存、`run_meta.counters` 短名与 `_count` 命名混用），导致前后端联调成本上升、历史结果兼容逻辑分散、回归测试口径不稳定。需要将产物协议收敛为唯一标准，并明确兼容窗口，避免后续持续返工。

## What Changes

- 统一回测产物协议的标准命名：`reason_codes.csv` 作为唯一标准文件名。
- 统一 `run_meta.counters` 的标准字段为短名：`raw_signal/blocked/orders/skipped/closed_trades`。
- 明确 `symbol_performance.csv` 为必出产物（允许空文件）。
- 明确缺失产物处理策略：写空文件，并在 `run_meta.missing_fields` 标注缺失来源。
- 建立两版本兼容窗口：读取侧兼容历史命名（旧文件名与旧字段名），写入侧统一输出新标准。
- 同步更新协议文档与测试契约，确保“文档-实现-测试”一致。

## Capabilities

### New Capabilities
- `artifact-protocol-convergence`: 定义并执行回测产物协议收敛策略（标准命名、兼容窗口、缺失处理、契约校验）。

### Modified Capabilities
- `single-run-pipeline`: 更新标准产物协议与 `run_meta`/`rows` 的字段口径，确保单次运行输出与协议一致。
- `symbol-performance-ranking`: 将 `symbol_performance.csv` 提升为必出产物，并定义空产物与缺失标注行为。

## Impact

- 后端：`backend/api/endpoints/backtest_v2.py`、`backend/api/endpoints/backtest_v2_artifacts.py` 的产物写入与读取兼容逻辑。
- 前端：`frontend/assets/js/backtest_v2.js` 的 artifact 读取路径与字段回退逻辑。
- 文档：`docs/SCHEMA_rows.json.md`、`docs/SCHEMA_run_meta.json.md`。
- 测试：`tests/integration/test_schema_and_artifacts.py` 及相关协议/产物集成测试。
