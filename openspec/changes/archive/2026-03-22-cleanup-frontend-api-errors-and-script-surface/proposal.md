## Why

当前仓库已经完成一轮主边界重构，但前端大控制器、旧 API 兼容层、执行 compat shim 和顶层脚本过渡层仍然保留了较多历史实现。继续在这些残留层上叠加改动，会重新放大耦合，并增加 `V10.1` 这类价格型信号在后续清理中发生口径漂移的风险。

## What Changes

- 继续收缩桌面前端旧控制器，确保已拆出的配置、历史、加载、保存、运行职责由独立页面模块承载，旧文件只保留薄壳与必要 bootstrap。
- 继续清理 `backend/api/endpoints/*` 厚实现，将旧入口进一步压缩为薄 shim，避免新实现反向依赖 compat 模块。
- 继续推进执行 compat shim 删除路径，限制 `foundation_shell`、strict shim、`portfolio_builder.py` 和 legacy loop 的职责，只允许保留过渡所需的最小兼容面。
- 继续收缩顶层脚本面和工作区临时产物，确保已迁移脚本保持薄 wrapper 形态，未归档脚本不会重新长回大型主入口。
- 为上述清理补足静态边界测试、shim hygiene 测试和 `V10.1` 回归验证门，确保清理前后回测口径不漂移。

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `frontend-module-split`: 增加旧控制器退化为薄壳的要求，并要求提取出的页面模块成为唯一活跃实现。
- `http-surface-boundary-split`: 增加旧 `endpoints/*` 入口必须压缩为薄 shim、不得继续承载重型实现的要求。
- `execution-shell-unification`: 增加 compat shim 收缩和删除路径约束，禁止 legacy 执行链继续吸收新逻辑。
- `script-surface-governance`: 增加已迁移脚本必须保持薄 wrapper、工作区临时产物必须受控的要求。

## Impact

- 前端桌面工作台：
  - `frontend/assets/js/backtest_v2.js`
  - `frontend/assets/js/ui-controls.js`
  - `frontend/assets/js/artifacts.js`
  - `frontend/assets/js/pages/*`
  - `frontend/index.html`
- 后端 API 兼容层：
  - `backend/api/endpoints/*`
  - `backend/api/backtest_v2/*`
  - `backend/api/mobile/*`
- 后端执行兼容层：
  - `backend/core/engine_compat/foundation_shell.py`
  - `backend/core/engine_vector/portfolio_simulator_strict.py`
  - `backend/core/engine_vector/strict_runtime_impl.py`
  - `backend/core/portfolio/portfolio_builder.py`
  - `backend/core/portfolio/legacy_loop.py`
- 脚本和工作区治理：
  - `backend/scripts/*`
  - `.gitignore`
  - `tests/unit/*boundary*`
  - `tests/unit/*governance*`
