## Why

当前前端同时存在 preset、快速加载、隐藏下拉、`config_id` 覆盖草稿、`workbench_config` 直传等多条配置进入路径，用户无法判断“这次运行到底用的是哪份配置”。这不仅让前端交互混乱，也破坏了回测引擎“配置唯一真相”的研究纪律，因此需要先统一配置加载与运行时 handoff，再继续做前端大改。

## What Changes

- 新建单一“配置中心”入口，统一承载前端草稿、已保存配置、内置模板、candidate preset 的加载与切换。
- 将 `run_async` 与 `execution_preview` 统一为“单一运行真相”模式：每次运行只向后端提交一份 resolved runtime config json，`config_id` 仅保留为 provenance。
- 统一已保存配置的命名、分组与展示元数据，区分 `builtin / manual / script / candidate`，并消除同屏双入口加载。
- 为每次实验和执行预览补充运行来源说明，明确显示配置来自前端草稿、已保存配置还是锁定模板。
- **BREAKING**：前端不再依赖“同时传 `config_id` + `workbench_config`”的混合运行模式。

## Capabilities

### New Capabilities
- `workbench-config-center`: 定义前端唯一配置入口、配置中心分组、命名与来源显示规则。
- `runtime-config-handoff`: 定义运行前如何将当前来源解析为唯一的 runtime config json，并把 provenance 写入实验元信息。

### Modified Capabilities
- `single-run-pipeline`: 单次运行与执行预览的请求契约、冲突处理与返回元信息需要改为单一运行真相模式。

## Impact

- 前端：[`frontend/index.html`](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/index.html)、[`frontend/assets/js/backtest_v2.js`](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/backtest_v2.js)、[`frontend/assets/js/ui-controls.js`](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/ui-controls.js)
- 后端 API：[`backend/api/endpoints/_config_store.py`](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/_config_store.py)、[`backend/api/endpoints/_experiment_runner_api.py`](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/endpoints/_experiment_runner_api.py)
- 运行元信息与产物：`run_meta.json`、配置列表 API、执行预览返回
