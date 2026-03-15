## Why

当前仓库已经完成主边界重构，但仍保留 4 类会持续放大耦合的历史残留：新 API 目录仍依赖旧 `endpoints` helper 树、桌面结果区仍保留 Vue workbench 与 fallback DOM 双轨、脚本治理规则已建立但迁移完成度很低、运行时仍长期保留历史 artifact alias 归一化。继续在这些残留层上叠加功能，会削弱后续接入多资产时的可扩展性，并增加在后续清理中误伤 `V10.1` 口径的概率。

## What Changes

- 提取 `backend/api/endpoints/*` 中仍被新 API 边界复用的共享 helper，迁入独立 shared 层，使 `backend/api/backtest_v2/*` 与 `backend/api/mobile/*` 不再物理锚定在历史目录。
- 收紧桌面结果区渲染职责，使 Vue results workbench 成为生产主路径的唯一结果 owner，fallback DOM 仅保留为显式受控的开发/应急路径。
- 继续推进脚本面迁移，把高频研究脚本从顶层 `backend/scripts/*.py` 迁入 `study definition + CLI + generated thin script` 主路径，并缩小顶层活跃脚本面。
- 通过离线迁移工具清理历史 artifact / counter alias，在运行时只保留 canonical schema，避免长期在查询链路中常驻历史命名归一化。
- 为上述清理补齐静态边界测试、迁移审计和 `V10.1 -> exp_20260314_144548534_7db9` 回归门，确保清理前后结果不漂移。

## Capabilities

### New Capabilities
- `api-shared-helper-surface`: 定义 API shared helper 的正式宿主层，禁止新 API 边界继续依赖历史 `endpoints` 目录。
- `canonical-artifact-migration`: 定义历史 artifact 离线迁移和运行时只认 canonical schema 的要求。

### Modified Capabilities
- `frontend-module-split`: 继续收缩旧桌面控制器，使配置/历史/加载/保存/运行之外的剩余职责进一步外提，旧文件只保留薄壳与 bootstrap。
- `results-workbench-finalization`: 将 fallback DOM 明确降级为显式受控的开发/应急路径，生产主路径只允许 Vue workbench 持有结果区 DOM ownership。
- `script-surface-governance`: 增加脚本迁移完成度要求，限制顶层活跃脚本数量，并要求高频研究脚本优先迁入 study/CLI 主路径。

## Impact

- 后端 API 边界与共享基础设施：
  - `backend/api/backtest_v2/*`
  - `backend/api/mobile/*`
  - `backend/api/endpoints/*`
  - 新增 `backend/api/shared/*`
- 前端桌面工作台：
  - `frontend/assets/js/backtest_v2.js`
  - `frontend/assets/js/ui-controls.js`
  - `frontend/assets/js/artifacts.js`
  - `frontend/assets/js/pages/*`
  - `frontend/app/results-workbench/*`
  - `frontend/index.html`
- 研究命令面与脚本治理：
  - `backend/cli/*`
  - `backend/research/*`
  - `backend/scripts/*`
  - `research/studies/*`
- artifact 读写与迁移：
  - `backend/api/backtest_v2/protocol.py`
  - `backend/api/backtest_v2/data_impl.py`
  - `backend/core/services/experiment_query_service.py`
  - `outputs/**/*`
- 质量门与回归验证：
  - `tests/unit/*boundary*`
  - `tests/unit/*governance*`
  - `tests/unit/*protocol*`
  - `tests/integration/*artifacts*`
