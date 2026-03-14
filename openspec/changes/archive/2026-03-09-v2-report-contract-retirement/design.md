## 概述

这条 change 处理“报告协议最后一刀”。当前系统虽然已经在前端主线使用 Markdown/AI 分析报告，但后端和脚本仍保留 `report.html` 的公开 contract。这会造成：

1. 报告协议双轨并存
2. manifest 仍带 `html_export`
3. baseline compare 长期保留 `report.html` 诊断性 WARN

本 change 的目标是把 `report.html` 从当前主契约中退役，只保留 Markdown/AI 报告面。

## 目标

### 目标 1：Markdown 报告成为唯一主消费面

前端查看、复制、导出报告只使用 Markdown/AI 报告，不再通过 HTML 页面消费报告。

### 目标 2：移除公开 HTML 报告接口

`/api/backtest_v2/experiments/{exp_id}/report` 不再作为公开接口保留。

### 目标 3：门禁不再依赖 HTML 报告

baseline compare 和 consistency check 不再将 `report.html` 视为当前主契约的一部分，从而消除长期存在但无业务价值的 `WARN`。

## 非目标

以下内容不在本 change 范围内：

- 不改回测引擎和实验结果口径
- 不重写 Markdown 报告内容结构，只收口协议
- 不要求删除历史实验目录中的旧 `report.html` 文件

## 设计

### 1. 报告主契约

当前主契约收口为：

- 页面内 Markdown 报告
- `.md` 导出
- 供 agent 分析的结构化 Markdown 文本

`report.html` 即使保留在历史实验中，也不再作为当前 contract 的必需或推荐部分。

### 2. manifest 收口

manifest 中不再将 `report.html` 作为当前标准可选产物的一部分。若历史目录中存在 HTML 报告，可视为 legacy artifact，但不再暴露给当前主消费面。

### 3. 历史与导出

历史面板不再提供“查看 HTML 报告”入口。报告导出统一为 Markdown。

### 4. 脚本与门禁

baseline gate 与 consistency check 去掉对 `report.html` 的主路径依赖：

- 不再因 HTML hash 漂移产生 WARN
- 一致性检查转向 Markdown 报告、manifest、自身核心 artifact

## 风险与控制

### 风险 1：历史工具链仍依赖 HTML 报告

控制：

- 先迁当前 live caller
- 对历史目录保留文件但移出 contract

### 风险 2：前端导出体验退化

控制：

- Markdown 报告必须继续支持页面内查看、复制和导出
- 报告结构保持适合 GPT/agent 分析
