## Context

当前桌面前端已经把配置工作区、结果工作区、API adapter 与 orchestration 拆到 `desktop-shell/*`，但页面真正的主启动权仍由 `backtest_v2.js` 持有：它在脚本加载期创建共享 `state`，`index.html` 直接调用它暴露的 `init()`，测试 harness 也仍以它为主入口。结果是 owner map 在文档上成立，在实际装载链上却没有真正落地。

这次变更只处理宿主 owner：把共享 `state` 初始化与主启动分发切到新的 host/bootstrap owner，并让旧壳退回 compat shell。它不改变研究口径，也不一次性删除旧壳提供的 helper 与桥接能力。

## Goals / Non-Goals

**Goals:**
- 引入正式的 desktop host/bootstrap owner，成为页面主启动入口。
- 让共享 `state` 由新 host 创建，`backtest_v2.js` 改为复用而非覆盖。
- 让 `index.html` 与前端 harness 都优先走新的 host/bootstrap 装载链。
- 明确 `backtest_v2.js` 当前只剩 compat shell 身份，不再是主 bootstrap owner。

**Non-Goals:**
- 不在本次变更里完全删除 `backtest_v2.js`。
- 不在本次变更里把 `byId`、`esc`、`setHtmlById`、`toggleStatusPanel` 等 helper 全部迁走。
- 不修改运行配置编译逻辑、回测合同或研究结果口径。
- 不处理 unified combo 以外的前端 legacy 清理。

## Decisions

### 决策 1：新增 `desktop-shell/host.js` 作为正式 host owner
- 选择：新增 `frontend/assets/js/desktop-shell/host.js`，在脚本执行期创建共享 `state`，并暴露 `initDesktopAppHost()`。
- 原因：这是最小可控切口。它能先把 owner 身份从旧壳剥离，而不要求立刻迁出所有 helper。
- 备选方案：直接在 `desktop-shell/bootstrap.js` 中吸收这部分职责。
- 不选原因：`bootstrap.js` 当前定位是 shell attribute / boundary bootstrap，继续膨胀会把宿主初始化与 shell state 管理重新耦合。

### 决策 2：`index.html` 改为调用 host init，而不是直接调用 `init()`
- 选择：主入口从 `if (typeof init === 'function') init();` 改为 `if (typeof initDesktopAppHost === 'function') initDesktopAppHost();`。
- 原因：这样可以明确主启动 owner 已切换，同时仍允许 host 在内部委托 compat shell 的 legacy `init()`。
- 备选方案：保留 `index.html` 不动，只在运行时 monkey patch `window.init`。
- 不选原因：owner 身份仍然模糊，无法形成清晰的主链边界。

### 决策 3：`backtest_v2.js` 改为复用已有共享状态
- 选择：旧壳加载时优先复用 `window.state / window.__WB_STATE__`，只有缺失时才兜底创建。
- 原因：这样 host 成为单一 state owner，同时兼容非主链环境与旧测试。
- 备选方案：完全移除旧壳中的 state 初始化。
- 不选原因：会放大改动面，并立即要求所有非主链环境同步改造。

### 决策 4：前端 harness 同步到新的装载顺序
- 选择：`tests/frontend/multi_alpha_workbench_harness.cjs` 先执行 host，再执行 `backtest_v2.js` 与其余模块。
- 原因：测试主路径必须与真实页面装载链一致，否则 owner cutover 只有页面有效、测试仍停在旧模型。
- 备选方案：暂不改 harness。
- 不选原因：会让后续边界测试继续基于错误入口。

## Risks / Trade-offs

- [Risk] host 先于旧壳创建 `state` 后，旧壳仍有局部初始化代码假定自己是首个 owner → Mitigation：只切 `state` owner，不动旧壳其余 helper 与 `init()` 语义；旧壳只从“覆盖”改为“复用”。
- [Risk] `index.html` 切 host init 后，如果 host 没有成功装配 legacy init 委托，页面会直接失去启动能力 → Mitigation：host init 只做薄分发，明确兜底检查 `window.init` 是否存在。
- [Risk] harness 与页面顺序漂移导致边界测试结论失真 → Mitigation：同一轮内同步修改 harness 装载顺序。
- [Trade-off] 本次不会立刻消除 `backtest_v2.js` 的 helper 依赖 → Mitigation：后续以独立 change 继续迁出 helper/runtime surface。

## Migration Plan

1. 新增 `desktop-shell/host.js`，创建共享 `state` 并暴露 host init。
2. 调整 `index.html` script 顺序，让 host 在 `bootstrap.js` 与 `backtest_v2.js` 之前装配共享状态；DOM ready 时调用 host init。
3. 修改 `backtest_v2.js`，只复用已有共享状态，不再覆盖 host 创建的 state。
4. 修改前端 harness，使其先加载 host，再加载旧壳与其余模块。
5. 后续独立 change 再继续迁出 helper 与可视壳桥接逻辑。

回退路径：
- 删除 `host.js` 引入并恢复 `index.html` 直接调用 `init()`。
- 恢复 `backtest_v2.js` 的旧 state 初始化方式。
- 恢复 harness 直接从 `backtest_v2.js` 起步。

## Open Questions

- `backtest_v2.js` 内部的基础 helper 应该先抽到 `desktop-shell/runtime-surface.js`，还是按工作区逐步下沉？本次不决。
- 页面级 `init()` 里哪些职责应在下一轮从 compat shell 挪到 host，需要在切完 owner 后再做一轮静态拆分。
