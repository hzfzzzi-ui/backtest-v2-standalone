# markdown-analysis-report Specification

## Purpose
定义 Markdown 分析报告作为当前主报告面的契约。

## Requirements

### Requirement: Markdown 分析报告必须成为唯一主报告面
系统 MUST 提供 Markdown 分析报告作为唯一主报告面，供前端查看、复制、导出和 AI/agent 分析。当前主线 SHALL NOT 依赖 `report.html` 才能消费实验报告。

#### Scenario: 页面内查看报告
- **WHEN** 用户在结果工作台查看实验报告
- **THEN** 页面 SHALL 显示 Markdown 分析报告
- **THEN** 报告内容 SHALL 适合直接复制给 GPT/agent 分析

#### Scenario: 导出报告
- **WHEN** 用户点击导出报告
- **THEN** 系统 SHALL 导出 Markdown 文件
- **THEN** 不再导出 HTML 页面
