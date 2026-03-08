## Why

公开运行与产物表面已经收敛，但仍有一批后端脚本和内部工具直接依赖旧模块路径、旧配置字段或原始目录读写习惯。这会阻断真正的旧代码淘汰，并且给系统留下重新长出“多真相输入/多真相消费面”的回潮入口。

## What Changes

- 盘点并分类所有仍在使用旧公开字段、旧 import 路径、原始 `results_dir`/`report.html` 读写习惯的脚本与工具。
- 新建 internal helper 契约，承接仍然需要内部兼容能力的脚本调用面，避免它们继续直接依赖 endpoint 私有实现。
- 迁移仍然直接调用公开旧表面的脚本；无法在本轮迁移的脚本进入冻结清单，不允许再长新逻辑。
- 形成第一批可安全删除的旧模块候选清单，并给出删除前置条件与回归门槛。
- **BREAKING**：后端脚本不再被允许通过公开 `run/run_async/preview` 表面携带旧配置字段；如仍需旧参数，必须走 internal helper 或进入冻结名单。

## Capabilities

### New Capabilities
- `script-runner-governance`: 约束后端脚本在公开表面收敛后的运行与产物消费方式。
- `internal-shim-boundary`: 定义 internal-only compatibility shim 的职责边界、调用者治理与退役门槛。

### Modified Capabilities
- `artifact-protocol-convergence`: 内部脚本与 helper 读取实验产物时，要求围绕 manifest 声明或显式 internal helper 工作，而不是继续把原始文件名或目录布局当成产品真相。

## Impact

- 影响脚本与工具：
  - `backend/scripts/run_alpha_v1.py`
  - `backend/scripts/baseline_regression_check.py`
  - `backend/scripts/run_clean_data_standard_reruns.py`
  - `backend/scripts/report_consistency_check.py`
- 影响内部兼容模块与产物边界：
  - `backend/api/endpoints/_experiment_runner_api.py`
  - `backend/api/endpoints/_config_governance.py`
  - `backend/api/endpoints/_candidate_presets.py`
  - `backend/api/endpoints/backtest_v2_artifacts.py`
  - `backend/core/report/report_generator.py`
- 影响文档与退役门槛：
  - `docs/ops/*`
  - 以 `exp_20260308_021045840_cde0` 为基线的回归门禁
