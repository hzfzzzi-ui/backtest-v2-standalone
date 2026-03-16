## Why

当前仓库虽然已经完成多轮边界重构，但仍残留一批以历史载体、过渡语义和超大文件形式存在的代码债，阻碍后续按多资产方向继续演进。既然当前正式锚点已经明确为 `baseline_V10.1 -> exp_20260314_144548534_7db9`，就应以该锚点为唯一回归门，系统性清除不再需要的前向兼容壳、过时研究入口和阻碍架构整洁性的残留层。

现在做这件事的原因很直接：前端仍未完全以 manifest/runtime snapshot 为真相，API surface 仍保留通用 artifact 读入口与历史 alias，顶层研究脚本仍是事实上的第二套入口，`backend/core` 中多个热点文件已经大到会直接妨碍后续接入美股 ETF、加密现货和防守层资产。继续拖延，只会让新资产接入在旧载体上继续长债。

## What Changes

- **BREAKING** 删除前端主路径对历史 fallback 结果面和通用 `/api/backtest_v2/artifacts/read` 依赖，桌面研究页只保留 `desktop-research-page -> runtime snapshot -> Vue workbench` 一条结果主链。
- **BREAKING** 将前端运行真相进一步从 `input_source_meta/config_id` 过渡到 `experiment manifest / runtime snapshot`，配置来源降级为辅助 provenance，不再作为主运行语义。
- **BREAKING** 删除过时顶层 `backend/scripts/run_*_research.py` 研究入口；已过时研究直接删除，保留研究主路径为 `research/studies/*.study.yaml + backend/scripts/generated/run_<study>.py`。
- 收口并瘦身 `backend/api/backtest_v2`：移除主路径中的历史 artifact alias/fallback 读取语义，主 surface 只消费 canonical schema 与明确 section 接口。
- 新增一轮 `backend/core` 热点文件职责拆分，优先处理超大文件与混合职责文件，但不得改变 `baseline_V10.1` 的执行时点、成交口径和结果。
- 清理剩余乱码文案、死分支、过渡 helper、仅为历史兼容而存在的 UI/API/schema 代码。
- 将本轮清理严格锚定 `baseline_V10.1`，任何会导致 `exp_20260314_144548534_7db9` 结果漂移的改动都必须拒绝或回退。

## Capabilities

### New Capabilities
- `core-hotspot-modularization`: 在不改变 `baseline_V10.1` 结果的前提下，对 `backend/core` 超大热点文件进行职责拆分和结构收口。

### Modified Capabilities
- `http-surface-boundary-split`: 前端主路径不再依赖通用 artifact 读接口，HTTP surface 收口为 manifest/surface/section/专用接口。
- `runtime-boundary-contracts`: 前端和查询层的主真相从配置来源转向 experiment manifest / runtime snapshot，并删除不再需要的前向兼容语义。
- `results-workbench-finalization`: 结果区彻底收敛为 Vue workbench 单 owner，移除历史 fallback 结果面与相关残留。
- `frontend-module-split`: 进一步拆分前端旧壳，将配置草稿构建、来源语义和结果消费逻辑从过渡文件中抽离并瘦身。
- `script-surface-governance`: 顶层研究脚本继续退场，study + generated thin script 成为唯一正式研究入口。
- `canonical-artifact-migration`: 历史 artifact alias 迁移完成后，运行时只认 canonical schema，不再为旧名字保留常驻兼容读取。
- `study-definition-runner`: 扩大 study 覆盖面并默认生成正式 thin script，停止依赖顶层 `_research.py` wrapper。

## Impact

- 影响目录：`frontend/assets/js/*`、`frontend/app/results-workbench/*`、`backend/api/backtest_v2/*`、`backend/core/*`、`backend/research/*`、`backend/scripts/*`、`research/studies/*`、`tests/*`。
- 影响接口：桌面主路径的结果获取方式、artifact schema 读取约束、study 执行入口。
- 影响研究治理：一批已过时研究脚本将被删除，inventory 与 study 资产同步更新。
- 风险边界：不得改动 `baseline_V10.1` 的信号时点、执行时点、成交规则、统计口径；所有清理必须以前后对照 `exp_20260314_144548534_7db9` 为回归门。
