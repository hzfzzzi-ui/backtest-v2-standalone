## 1. P0 基线冻结与收口门建立

- [x] 1.1 固化 `baseline_V10.1` 的回归锚点与本轮阻断条件。DoD：形成可执行的回归命令、预期快照和“哪些漂移必须回退”的清单；验证：本地运行一次主线回归检查并记录结果；风险：把结构变化误判为口径变化。
- [x] 1.2 增加 `P0` 通过门检查清单。DoD：默认 `pytest` collect、关键治理测试、主线回归三类门有明确检查项；验证：以文档或自动断言形式可重复执行；风险：门太宽导致收口后仍留暗债。

## 2. P0 测试与脚本面收口

- [x] 2.1 修复当前默认测试集在 collect 阶段失败的 `CSI1000` 相关脚本导入面。DoD：失败测试改为依赖正式 CLI/managed/wrapper surface；验证：`pytest -q` 至少完成 collect；风险：仅改测试不改正式入口定义。
- [x] 2.2 更新 `backend/scripts/inventory.json`、README 与治理测试，使脚本迁移后的正式宿主关系可审计。DoD：inventory、README、governance tests 一致；验证：相关 unit tests 通过；风险：文档与真实宿主再次漂移。

## 3. P0 正式入口单一化

- [x] 3.1 明确 `backend/cli`、`backend/cli/managed`、`backend/scripts/generated` 与 `backend/core/cli` 的正式/兼容角色。DoD：代码路径、README、测试对同一入口定义一致；验证：CLI 相关测试与脚本治理测试通过；风险：双入口继续并存但没有人知道哪套是正式面。
- [x] 3.2 对 `backend/core/cli` 采取显式退场策略。DoD：降级为兼容壳或停止作为正式入口；验证：文档与入口测试不再把它当主面；风险：历史调用路径静默失效。

## 4. P0 桌面前端 owner 收口

- [x] 4.1 为 `legacy shell / config draft core / Vue results workbench` 建立显式 owner map 与边界测试。DoD：能证明结果区与配置编译各有唯一 owner；验证：前端边界测试或静态断言通过；风险：多 owner 继续写同一块可见 DOM。
- [x] 4.2 将旧壳文件继续收缩到 bootstrap、桥接和轻量控件联动。DoD：`backtest_v2.js`、`ui-controls.js` 不再重新吸收结果拼装或配置编译主逻辑；验证：桌面页基础交互仍可用，Vue 结果区正常挂载；风险：为求快把新逻辑又堆回旧壳。

## 5. P1 API 与应用服务边界收口

- [x] 5.1 识别并下沉 `backend/api/backtest_v2` 中可复用的运行编排、snapshot 组装和真相构建逻辑。DoD：对应实现迁入 `core.services` 或 `core.tools`，公共 route 语义不变；验证：公共 surface/runner 相关单测通过；风险：内部迁移引起路由语义漂移。
- [x] 5.2 为 API 拆分补齐回归测试。DoD：公共路径、请求契约、基础响应语义有回归断言；验证：相关 unit/integration tests 通过；风险：只完成文件拆分却没有边界保护。

## 6. P1 文档、协议与示例同步

- [x] 6.1 补齐当前目录树与模块职责文档。DoD：形成与仓库现实一致的 `ARCHITECTURE` 级文档；验证：文档覆盖主路径、过渡路径、正式入口和运行链；风险：文档再次抽象化、失去约束力。
- [x] 6.2 补齐守则引用的 schema 文档与 example/runbook。DoD：`run_meta`、`rows`、`manifest` 等正式协议文档和示例路径实际存在；验证：守则引用路径全部可打开且内容与当前协议一致；风险：补文档时引入新的口径歧义。

## 7. P1 收口验收与回退准备

- [x] 7.1 运行一轮 `P0/P1` 总验收。DoD：默认 `pytest` collect、关键治理测试、API 边界测试、主线回归全部通过；验证：保留可复现命令和结果摘要；风险：只验证局部通过，遗漏总链路回归。
- [x] 7.2 形成回退与后续 apply 说明。DoD：明确每个波次失败时的回退动作、不可继续推进的条件和下一步 apply 入口；验证：change 文档可直接指导实现；风险：进入 apply 后再次边做边想。
