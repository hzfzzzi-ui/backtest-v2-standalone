## Context

前端文档层已经把桌面架构定为：

- 单页 desktop app
- 顶层模块：
  - `desktop_shell`
  - `config_workspace`
  - `run_orchestration`
  - `results_workspace`
  - `status_center`
- 单一顶层 app state
- UI 组件不得直接直连 API

当前实现还停留在旧壳主导的过渡期：

- `backtest_v2.js` 仍持有启动权
- `desktop-*.js` 页面控制模块仍持有大量宿主职责
- `results-workbench-bridge.js` 仍是结果真相中继层
- 旧 state slice 仍挂在全局窗口对象上

本次 change 是 L2/L3 之间的前端架构收口：只先把目标壳、模块边界和迁移顺序定死，不在本次 change 中重做复杂路由、导出或高级比较功能。

## Goals / Non-Goals

**Goals**

- 固定新 desktop app 的宿主边界
- 固定顶层模块和 app state 架构
- 固定旧壳与 bridge 的过渡定位
- 固定共享 API adapter 边界

**Non-Goals**

- 不在本次 change 中实现历史实验高级对比
- 不在本次 change 中实现导出功能
- 不在本次 change 中引入复杂路由
- 不在本次 change 中让移动端承担写操作

## Decisions

### 1. 新桌面端是单页 desktop app

正式桌面端采用单页应用形态，不引入正式前端路由作为首批重构前提。

### 2. `results-workbench` 只是 `results_workspace` 子模块

结果工作台继续保留，但正式上降级为结果区子模块，不再承载整页宿主语义。

### 3. 单一 app state + 领域切片

新桌面 app 采用单一顶层状态树，按领域切分：

- `config_workspace`
- `run_orchestration`
- `results_workspace`
- `status_center`
- `desktop_shell`

旧 state slice 只保留为迁移原型，不保留实现。

### 4. 旧壳/bridge/旧 helper 全部是过渡层

以下对象正式上只保留迁移期定位：

- `backtest_v2.js`
- `ui-controls.js`
- `artifacts.js`
- `results-workbench-bridge.js`
- `frontend/assets/js/pages/desktop-*`

## Risks / Trade-offs

- 若新壳接管顺序错误，配置、运行、结果三条链会相互打断
- 若 API adapter 边界不先固定，UI 重构会继续沿旧 helper 扩张
- 若过早删除 bridge，会打断结果工作台迁移

## Migration Plan

1. 先建正式 desktop app 壳与模块/状态文档
2. 再把 API adapter 与 app state 收口
3. 然后按 `config -> run -> results -> status` 顺序迁移
4. 最后删除旧壳、旧 bridge 和旧控制模块

## Rollback

- 允许新壳与旧壳在迁移期并存
- 如新壳接管失败，可临时保留旧壳主入口并旁挂新模块
