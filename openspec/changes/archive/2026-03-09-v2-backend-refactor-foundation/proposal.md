## Why

当前后端仍同时保留多配置来源、多执行分支和结果兼容补丁层，导致“配置真相、执行真相、产物真相”并不唯一。  
在 `exp_20260308_021045840_cde0` 已被明确指定为锁定基线的前提下，后续任何后端重构都必须先建立逐步回归门禁和兼容迁移壳，否则清理旧代码时很容易在不自知的情况下改变回测结果。

## What Changes

- 建立以 `exp_20260308_021045840_cde0` 为基准的后端重构基线契约，明确哪些实验产物必须逐项保持不变，哪些运行元字段允许漂移。
- 新增“基线等价性回归门禁”，要求所有触及配置解析、数据预加载、引擎编排和产物写盘的改动，都必须先复跑同一输入并与锁定基线逐文件比较。
- 定义新的后端主线兼容壳：前端只提交一份语义 `config_json`，后端编译为内部 runtime plan，再调用兼容执行层，保证在重构初期结果完全等价。
- 将数据库访问边界前移到预加载阶段，定义只读 `DataBundle` 作为引擎输入，禁止在日循环中再次查库。
- 收敛实验结果真相：后端继续以单个 `experiment_id` 目录产出标准文件集，但兼容壳阶段不得改变既有核心产物口径。
- 规划旧入口、多运行路由和结果补丁层的分阶段淘汰条件，但本 change 不直接删除所有旧代码。

## Capabilities

### New Capabilities
- `baseline-equivalence-gate`: 定义锁定基线实验、逐文件对比规则和重构阶段的放行门禁。
- `semantic-config-runtime-compiler`: 定义前端语义 `config_json` 到后端 runtime plan 的唯一编译路径。
- `engine-compatibility-shell`: 定义新后端主线与旧计算核之间的兼容执行壳，要求重构早期结果完全等价。

### Modified Capabilities
- `single-run-pipeline`: 运行入口改为围绕单一语义配置和单一实验目录组织，并要求新旧路径具备等价验证能力。
- `pipeline-data-integrity`: 数据预加载、缓存和时间对齐要求扩展到 `DataBundle` 边界，明确日循环内禁止查库。
- `artifact-protocol-convergence`: 产物协议需要支持基线比较、配置快照分层和稳定 manifest，但不得破坏当前前端依赖的核心文件名与语义。

## Impact

- 影响后端 API 入口与配置解析层，主要集中在 `backend/api/endpoints/` 下的实验运行和结果读写逻辑。
- 影响回测执行编排层，主要集中在 `backend/core/tools/experiment_runner.py`、`backend/core/portfolio/portfolio_builder.py` 和 `backend/core/engine_vector/`。
- 影响实验产物协议、基线回归脚本和相关测试，需要新增面向锁定基线的自动比较能力。
- 不引入新的外部服务依赖；主要新增的是内部契约、比较工具和兼容迁移边界。
