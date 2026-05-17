## Why

当前研究过程主要散落在对话、`outputs/` 运行产物和 study conclusion registry 中，缺少一个可长期追踪、可审计、可回滚的研究轮次账本。现在需要新增一个研究日志页面，把每一轮 study 的问题、主变量、证据、审计状态、结论和下一步固化下来。

## What Changes

- 新增 research-only 的 study journal 持久化能力，用于记录每一轮研究的重点、证据链接、审计检查和决策。
- 新增确定性自动总结能力，从研究轮次字段、关联实验和 study conclusion registry 中生成摘要草案、风险提示和下一步建议。
- 新增 `/api/research/study-rounds` 系列 API，支持列表、详情、新建、更新、追加笔记、关联实验和刷新自动总结。
- 新增 `/api/research/study-conclusions` API，读取现有 `outputs/studies/conclusions/**/registry.jsonl` 作为证据候选。
- 新增桌面研究日志页面 `/study-journal`，用于查看、创建和维护研究轮次。
- 明确该页面和自动总结不参与回测执行、不修改 baseline、不改变 study runner 语义。

## Capabilities

### New Capabilities

- `study-journal-surface`: 定义研究轮次日志、证据索引、确定性自动总结、研究日志 API 和桌面页面的正式边界。

### Modified Capabilities

- 无。

## Impact

- 影响范围：
  - `backend/research/`
  - `backend/api/`
  - `backend/main.py`
  - `frontend/`
  - `research/study_journal/`
  - `tests/`
- 不影响范围：
  - `baseline_V10.1`
  - `CN_STOCK_ETF_FORMAL_V1`
  - 回测执行时点、信号时点、成交时点
  - study runner 执行语义
  - `outputs/` 作为运行产物的边界
- 新增持久化文件位于 `research/study_journal/rounds/*.json`，用于长期研究知识沉淀；`outputs/studies/conclusions/**/registry.jsonl` 只作为证据来源读取。
