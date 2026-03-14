## 概述

这条 change 的目标不是继续美化页面，而是把结果工作台从“Vue 壳 + legacy 全局 helper”过渡态，收口成“Vue 单一 owner + legacy 仅 fallback”的稳定结构。

当前最主要的问题有三类：

1. Vue 组件仍依赖 `window._finalBuildStageRows`、`window.renderUnifiedStageFunnel`、`window.reasonByPrefix`、`window.buildAgentMarkdownReport` 这类全局 helper。
2. 结果区 accordion 仍由多个原生脚本同时改同一批 DOM，状态源不唯一。
3. legacy 渲染函数虽然已加 mounted guard，但仍保留较多直写结果区 HTML 的 active 路径，后续维护风险高。

本 change 只收前端结果区 ownership，不改变 artifact 协议，不改变回测计算，不改变 `baseline_V1` 与 `exp_20260308_021045840_cde0` 的展示数值来源。

## 目标

### 目标 1：Vue 结果工作台成为唯一结果区 owner

结果工作台在挂载成功后，以下区域只能由 Vue 渲染：

- 结果概览
- KPI 卡片
- 主图表
- 个股排名
- 9 阶段漏斗
- 交易明细
- AI Markdown 报告

legacy JS 只能负责：

- artifact 读取与归一化
- bridge snapshot 更新
- Vue 挂载失败时的显式 fallback

### 目标 2：结果区格式化逻辑本地化

将以下逻辑从 `window.*` helper 迁移为结果工作台内部纯模块：

- 漏斗阶段行构造
- 退出原因分组
- AI Markdown 报告拼装
- 结果数值格式化

这些函数必须通过 import 使用，而不是通过全局变量挂载。

### 目标 3：结果区状态源唯一

accordion、dock、结果区展开状态必须统一由一套状态源驱动。原生 `details/open`、`wb-open` 类名和直接 DOM 隐藏逻辑不能继续多处并存。

## 非目标

以下内容不在本 change 范围内：

- 不改后端回测引擎和基线收益口径
- 不改 artifact 字段名与 manifest 协议
- 不接管左侧配置抽屉
- 不做整页 Vue 重写

## 设计

### 1. 结果桥接层

保留一个轻量 bridge，将 artifact 读取结果写入一个结构化快照对象，例如：

```text
resultsSnapshot
  - overview
  - perf
  - chart
  - symbolRanking
  - stageFunnel
  - trades
  - agentReport
```

Vue 壳只消费这份快照。`artifacts.js` 不再负责生成结果区 HTML。

### 2. 纯模块格式化

在 `frontend/app/results-workbench/helpers/` 下新增或收口纯函数模块：

- `stageFunnelFormatting`
- `reportFormatting`
- `resultsFormatting`

这些模块只接收归一化后的 artifact/snapshot 数据，输出可直接供组件消费的 view model。

### 3. fallback 策略

fallback 只允许发生在“Vue mount 失败”这一种情况：

- Vue mount 成功：legacy 结果区 `hidden + inert + aria-hidden`
- Vue mount 失败：允许 legacy 结果区重新接管

不允许出现“Vue 已挂载，但 legacy 函数仍直接 patch 可见结果区 DOM”的情况。

### 4. accordion 状态

accordion 状态统一到结果工作台单一状态源：

- 哪个面板展开
- 是否默认收起
- dock 切换如何打开目标面板

`backtest_v2.js` 和 `ui-controls.js` 不得继续并行改同一批结果区节点的 `wb-open` / `hidden`。

### 5. 验证

功能完成后，至少验证：

- `baseline_V1` 默认加载
- `exp_20260308_021045840_cde0` 历史实验加载
- 100% 缩放下，结果区不发生横向溢出、折叠错位、主图遮挡
- 个股排名、9 阶段漏斗、交易明细可正常展开
- KPI、图表、漏斗、AI Markdown 报告数值与当前基线一致

## 风险与控制

### 风险 1：前端 owner 切换导致显示缺项

控制：

- 先保留 bridge snapshot，再迁组件消费
- 只在 Vue 挂载成功后隐藏 legacy 结果区

### 风险 2：100% 缩放下再次出现布局错位

控制：

- 将 100% 缩放 smoke 写入 tasks
- 以 `baseline_V1` 作为固定人工验收对象

### 风险 3：结果口径漂移

控制：

- 本 change 禁止改 artifact 字段解释
- 只允许改 owner 和 view model，不允许改数据来源
