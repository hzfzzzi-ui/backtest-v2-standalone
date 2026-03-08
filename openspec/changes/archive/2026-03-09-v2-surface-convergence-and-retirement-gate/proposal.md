## Why

当前后端内部执行主链已经基本收敛，但公开表面仍然同时暴露 `config_json`、`config_id`、`runtime_config_json`、`workbench_config`、`config_path` 等多种配置入口，实验读取侧也仍然混用 `results_dir`、`report.html` 和历史兼容补丁层。  
这会继续制造“输入真相”和“消费真相”的漂移，阻碍旧入口、旧报告层和旧配置存储层的正式收敛与淘汰。

## What Changes

- 新建公开运行表面契约：单次回测公开入口只接受前端语义 `config_json`，成功后以 `experiment_id` 作为唯一公开标识返回。
- **BREAKING**：公开运行与 preview 接口对 `config_id`、`runtime_config_json`、`workbench_config`、`config_path` 等配置变异字段改为显式拒绝；旧兼容逻辑只允许保留在内部迁移/基线脚本路径，不再作为产品真相。
- 统一实验产物消费面：公开读取入口围绕 `experiment_id -> manifest.json -> artifact` 组织，不再要求前端或脚本直接提供 `results_dir`。
- **BREAKING**：`report.html` 从主消费面降级为可选导出物；历史列表、实验加载、实验对比与产物读取在 `report.html` 缺失时仍必须可用。
- 固化旧表面淘汰门槛：把 `_config_store`、`_candidate_presets`、`_experiment_history`、旧 artifact 兼容补丁层纳入冻结范围，并定义何时允许删除。

## Capabilities

### New Capabilities
- `public-run-surface`: 定义公开回测运行与公开实验产物读取的唯一表面，包括 `config_json` 输入真相、`experiment_id` 输出真相，以及基于 `manifest` 的产物发现方式。

### Modified Capabilities
- `single-run-pipeline`: 公开单次运行入口改为只接受语义 `config_json`，并将 `experiment_id` 作为主要返回值与后续消费锚点。
- `artifact-protocol-convergence`: `manifest.json` 必须成为标准产物发现入口，公开消费不得再依赖隐式文件猜测或 `results_dir` 传入。
- `experiment-history`: 历史列表、删除、加载与比较必须围绕实验目录和标准产物工作，不得把 `report.html` 视为前置条件。
- `experiment-compare`: 实验对比入口必须通过 `manifest` 解析标准产物，不能继续绕过 manifest 直接猜测 `perf.json`/`nav.csv`。
- `backtest-report-export`: `report.html` 改为可选导出物；当报告缺失时，公开导出行为必须显式降级，而不是阻断实验主流程。

## Impact

- 影响公开 API 表面，主要集中在 `backend/api/endpoints/_experiment_runner_api.py`、`backend/api/endpoints/backtest_v2.py`、`backend/api/endpoints/_experiment_history.py`、`backend/api/endpoints/_config_store.py`、`backend/api/endpoints/_candidate_presets.py`。
- 影响实验产物发现与历史读取逻辑，主要集中在 `manifest.json`、artifact read 路由与历史/比较接口。
- 影响前端工作台和任何调用公开 API 的脚本；但引擎计算核、基线执行口径和 `exp_20260308_021045840_cde0` 的结果要求保持不变。
- 不引入新外部依赖；主要新增的是公开表面契约、兼容冻结规则和删除前置门槛。
