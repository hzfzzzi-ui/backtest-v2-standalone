# frontend/AGENTS.md

## 1. 定位

`frontend/` 是本仓库的展示与交互层，不是研究引擎，不是运行时真相层，也不是执行决策层。

前端当前正式职责只有三类：

- 承载桌面研究工作台与移动端入口
- 消费后端输出的结构化结果、审计和配置合同
- 管理前端 UI 状态、交互流程与 API adapter 协调

## 2. 当前正式主链

桌面前端当前正式主链为：

1. `frontend/index.html`
2. `frontend/assets/js/desktop-shell/host.js`
3. `frontend/assets/js/desktop-shell/runtime-surface.js`
4. `frontend/assets/js/desktop-shell/app-shell.js`
5. `frontend/assets/js/desktop-shell/*workspace.js`
6. `frontend/app/results-workbench/`

## 3. 前端硬约束

前端不得：

- 在浏览器中重算核心研究逻辑
- 在前端重新定义 runtime 真相
- 为展示方便回写或污染研究口径
- 把 `outputs/` 当成源码路径继续扩展逻辑
- 把非主链文件重新拉回主装载链

前端可以做：

- 展示、过滤、排序显示
- 本地 UI 状态控制
- 结构化结果视图拼装
- 通过统一 API adapter 发起受控请求

## 4. 当前边界

- `host.js`：共享状态 bootstrap owner
- `runtime-surface.js`：共享 helper/runtime owner
- `app-shell.js`：页面级 init / bridge / 事件装配 owner
- `desktop-shell/*workspace.js`：各工作区 active owner
- `frontend/app/results-workbench/`：结果工作台可见渲染 owner

## 5. 非主链文件规则

任何不在当前正式主链中的文件，都不得被描述为 active owner、bootstrap owner 或运行时真相 owner。

## 6. 修改输出要求

凡是非微小改动，默认都要说明：

1. 改了什么
2. 为什么改
3. 影响了哪些模块
4. 有什么风险
5. 如何验证
6. 如何回退

如果涉及前端主链、配置合同、结果真相或页面装载顺序，必须先说明边界是否发生变化。
