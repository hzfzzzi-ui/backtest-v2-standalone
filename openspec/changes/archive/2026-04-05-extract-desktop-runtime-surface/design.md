## Context

第一阶段已经完成 host owner cutover，但 `api-client.js`、`config-draft-core.js`、`config-workspace.js`、`load-orchestration.js`、`history-workspace.js`、`results-workspace.js` 等文件仍直接依赖 `backtest_v2.js` 中的全局 helper 与 runtime function。只要这些函数还停在旧壳里，旧壳就仍然是事实上的 shared runtime surface owner。

这次变更的目标不是继续拆业务逻辑，而是把所有“被多个脚本共用、且不应再挂在旧壳上”的 runtime surface 抽成正式模块，供 host/bootstrap 之后的主链脚本统一复用。

## Goals / Non-Goals

**Goals:**
- 新增正式 `runtime-surface.js`，承接跨模块共享的前端 runtime surface。
- 让 `state` 词法绑定在 host 之后由正式模块建立，而不是由 `backtest_v2.js` 建立。
- 让 `api-client.js`、`config-draft-core.js`、`config-workspace.js`、`load-orchestration.js`、`history-workspace.js`、`results-workspace.js` 的 shared dependency 不再来自旧壳。
- 让 `backtest_v2.js` 继续收缩为 compat shell。

**Non-Goals:**
- 不在本次变更中迁出旧壳所有页面级 init 逻辑。
- 不修改回测运行、配置编译或结果合同。
- 不重构 Vue results workbench。
- 不处理移动端脚本中的同名 helper。

## Decisions

### 决策 1：以单一 `runtime-surface.js` 承接当前 shared frontend runtime
- 选择：新增 `frontend/assets/js/desktop-shell/runtime-surface.js`，承接当前被多个脚本共用的 runtime surface。
- 原因：这些函数本来就是跨模块 shared dependency，分散迁移会留下多轮不稳定过渡期。
- 备选方案：按函数类别拆成多个小文件。
- 不选原因：当前目标是尽快让旧壳退出 shared runtime owner 身份，过早继续细拆只会增加切换面。

### 决策 2：本轮只迁“跨模块依赖面”，不迁页面级 init 细节
- 选择：迁出 `state` 词法绑定、基础 helper、asset/runtime source helper、results workbench bridge helper；保留 bootstrap source 解析、load menu 具体组装和页面 init 在 `backtest_v2.js`。
- 原因：这能最大化降低旧壳依赖，同时避免一次性触碰页面级流程控制。
- 备选方案：把 `backtest_v2.js` 整体继续拆到多个模块。
- 不选原因：超出当前阶段最小目标，且风险明显更高。

### 决策 3：`index.html` 与 harness 统一先加载 runtime surface
- 选择：`runtime-surface.js` 在 host 之后、其余依赖脚本之前加载；harness 保持同样顺序。
- 原因：这样共享 helper 与 `state` 词法绑定在主链上有单一确定来源。
- 备选方案：保留 `backtest_v2.js` 为 fallback owner，只在模块缺失时读取。
- 不选原因：会继续让旧壳成为隐式依赖源。

## Risks / Trade-offs

- [Risk] 一次迁出的函数较多，若遗漏某个依赖会导致页面级 `ReferenceError` → Mitigation：只迁出已通过静态搜索命中的跨文件依赖面，并同步调整脚本顺序。
- [Risk] `state` 词法绑定迁出后，旧壳和 harness 若仍按旧顺序加载会失效 → Mitigation：同一轮内同步改 `index.html` 与 harness。
- [Trade-off] `runtime-surface.js` 会暂时偏大 → Mitigation：等旧壳依赖完全退出后，再按功能分组细拆。

## Migration Plan

1. 新增 `runtime-surface.js`，复制当前跨模块依赖的 shared runtime surface。
2. 在 `index.html` 中将其放到 host 之后、其余依赖脚本之前加载。
3. 在 harness 中同步先加载 `runtime-surface.js`。
4. 从 `backtest_v2.js` 删除对应重复定义，只保留 compat shell 专属逻辑。
5. 下一轮再继续迁出页面级 init/helper，最终推动旧壳退出主装载链。

回退路径：
- 删除 `runtime-surface.js` 引入。
- 恢复 `backtest_v2.js` 内原有 shared runtime function 定义。
- 恢复 harness 旧装载顺序。

## Open Questions

- `runtime-surface.js` 之后是否应继续按 `dom-helpers`、`asset-runtime-surface`、`results-bridge-surface` 再拆分？本次不决。
