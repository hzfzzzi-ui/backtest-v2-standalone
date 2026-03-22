## Why

当前系统的 `universe.filters` 已经覆盖 ST、停牌、上市天数、流动性和价格过滤，但没有显式的科创板过滤开关。研究时如果需要排除科创板，只能改自选股票池或在外部做一次性裁剪，这会让股票池口径变成隐式行为，既不利于审计，也容易让前端草稿、验证接口和真实回测执行出现不一致。

这个需求会直接影响股票池/可交易池口径，属于高风险改动，因此必须把过滤行为收敛到现有共享 filter 链路中，并保持默认关闭，避免在未显式选择时改变 `baseline_V10.1` 的现有行为。

## What Changes

- 在 `universe.filters` 新增显式科创板过滤开关，默认值为关闭，只有用户主动启用时才排除科创板标的。
- 将科创板过滤接入现有共享 universe filter 链路，保证验证接口、数据 bundle 构建和真实回测运行使用同一口径。
- 前端研究台新增对应 UI 开关，并保证配置草稿构建、配置回填、语义配置校验与运行时编译全链路透传该字段。
- 为过滤结果补充最小可观测输出，确保 `excluded_counts` / `filters_config` 等现有元数据能反映科创板过滤是否生效。
- 补充后端单元测试与前端 workbench 回归测试，验证默认关闭不改现有行为、开启后能稳定排除科创板标的。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `universe-resolver`: 共享 universe filter 链路需要支持可选的科创板排除，并把过滤结果写入现有 universe 元数据。
- `universe-ui-binding`: 股票池基础过滤区需要新增科创板开关，并保证草稿构建与配置回填的前后端一致性。
- `api-runtime-config-compilation`: 语义配置校验与运行时编译需要保留并透传新的 universe filter 字段，确保真实回测执行口径与前端草稿一致。

## Impact

- 受影响代码主要在 `backend/core/universe/*`、`backend/core/tools/runtime_data_access.py`、`backend/core/tools/data_bundle_builder.py`、`backend/core/tools/experiment_runner.py`、`backend/api/backtest_v2/*`、`frontend/index.html`、`frontend/assets/js/*` 与对应测试文件。
- 不新增独立 API，也不修改默认 baseline 配置值；默认行为保持不变，仅扩展 `universe.filters` 的可选字段。
- 该改动会影响验证结果、运行期股票池过滤和前端配置协议，因此必须同步更新语义 schema、运行时编译和 UI 回填测试。
