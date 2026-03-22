## Why

当前仓库已经具备 A 股主线平台化骨架，但仍残留一批会直接阻碍后续 change 安全推进的 `P0/P1` 架构债务：默认测试集不能稳定 collect、正式入口仍有双轨、桌面前端仍处于旧壳和 Vue 岛混合态、API 包继续承接过多应用编排职责、架构守则与仓库现实未完全对齐。若不先完成这一轮收口，后续无论是主线研究推进还是多资产边界扩展，都会继续叠加在过渡层上，放大口径漂移和回归不可控风险。

现在做这件事的原因很直接：当前正式锚点已经明确为 `baseline_V10.1`，而本轮收口不改变研究口径，只处理入口、边界、治理和文档一致性问题，最适合作为下一阶段 change 的前置闸门。

## What Changes

- 建立一轮明确的 `P0/P1` 收口路线，将“必须先修的运行边界问题”和“可以紧随其后的结构收口问题”分成两个波次推进。
- `P0` 聚焦四件事：修复默认测试集 collect 失败、收口正式 CLI/脚本入口、冻结旧桌面壳的 owner 边界、补足主线回归门与治理测试。
- `P1` 聚焦四件事：继续拆分 `backend/api/backtest_v2` 的混合职责、补齐架构/协议文档与示例、收紧 manifest/runtime snapshot 主真相边界、继续压缩旧前端控制器的活跃职责。
- **BREAKING**: 未声明为正式命令面的历史脚本导入路径不再视为稳定内部接口；测试和工具必须迁移到正式 CLI/managed surface。
- **BREAKING**: 桌面结果主路径继续收口到 `experiment manifest / runtime snapshot / ResultsWorkbenchSnapshot`，旧壳文件不再允许重新吸收配置编译、结果拼装和重型渲染职责。
- 为上述收口增加显式完成门：`pytest` 默认测试集可 collect、主线治理测试通过、`baseline_V10.1` 回归结果不漂移、文档与仓库现实一致。

## Capabilities

### New Capabilities
- `architecture-closure-gates`: 定义 `P0/P1` 架构收口波次、验收门、禁止事项和回退要求。

### Modified Capabilities
- `script-surface-governance`: 将正式脚本面进一步收口到 CLI/managed/generated thin script，并要求默认测试不再依赖退役脚本实现。
- `frontend-module-split`: 将旧桌面壳继续退化为薄 bootstrap，明确结果区与配置编译的单一 owner 边界。
- `runtime-boundary-contracts`: 强化桌面主路径对 manifest/runtime snapshot 的依赖，防止配置来源重新成为页面唯一真相。
- `api-module-split`: 继续缩减 `backend/api/backtest_v2` 的混合职责，推动 route/contracts 与 runtime/application orchestration 分层。
- `test-infrastructure`: 增加默认 `pytest` collect 成功与关键治理测试稳定通过的要求。
- `architecture-doc`: 补齐当前代码架构、目录树、协议文档与运行示例，使文档与实际仓库结构重新对齐。

## Impact

- 影响目录：`backend/cli/*`、`backend/core/cli/*`、`backend/scripts/*`、`backend/api/backtest_v2/*`、`backend/core/services/*`、`frontend/index.html`、`frontend/assets/js/*`、`frontend/app/results-workbench/*`、`tests/*`、`docs/*`、`openspec/specs/*`。
- 影响接口：正式 CLI 入口、内部脚本导入面、桌面结果主路径、runtime snapshot/manifest 真相边界。
- 影响验证：默认 `pytest` collect、治理测试、`baseline_V10.1` 回归快照与主线产物协议检查。
- 不改变范围：本 change 不修改 `baseline_V10.1` 的研究口径、信号时点、执行时点、成交规则和资产池定义。
