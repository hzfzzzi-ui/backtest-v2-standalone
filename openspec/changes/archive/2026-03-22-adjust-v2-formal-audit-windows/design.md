## Context

当前 `audit_pams_ohlcv_daily_v2.py` 是单窗口执行器，它本身不维护“三窗口 formal audit 是否齐全”的上下文。`run_pams_ohlcv_daily_v2_full_backfill.py` 也只在末尾跑一次 `audit_full_window`，所以：

- formal audit 的三窗口没有被固定编排
- `2007-2017` 这一旧窗口仍残留在 spec 中
- 即使人工补跑过 `2016-2026` 或 `2007-2017`，结果也没有统一汇总入口

用户现在要求：

- 补齐 formal audit
- 把旧的 `2007-2017` formal audit 调整为 `2012-2017`

因此这次更合适的实现不是继续手工跑命令，而是补一层极薄的 formal audit runner。

## Goals / Non-Goals

**Goals**

- 把 formal audit 三窗口固化为常量和统一 runner。
- 把硬门槛窗口从 `2007-2017` 调整为 `2012-2017`。
- 让 `full_backfill` 自动产出 formal audit 汇总。
- 保持单窗口 audit 核心逻辑不变，避免牵动 canonical/runtime 规则。

**Non-Goals**

- 不修改 `audit_pams_ohlcv_daily_v2.py` 的字段口径或 gate 算法。
- 不重新设计 `pams_ohlcv_daily_v2_audit_daily` 的表结构。
- 不在本次变更中处理剩余 unresolved symbol。
- 不修改策略层三窗口研究纪律；本次只调整 `V2 formal audit` 口径。

## Decisions

### 1. 以常量定义 formal audit windows

在 `pams_ohlcv_daily_v2_common.py` 增加显式窗口定义：

- `2016_2026`: `2016-03-01 ~ OFFICIAL_END_DATE`
- `2012_2017`: `2012-01-04 ~ 2017-12-29`
- `2007_2026`: `DEFAULT_BACKFILL_START ~ OFFICIAL_END_DATE`

原因：

- 避免窗口日期散落在 runbook、命令和人工记忆里。
- 便于 runner、测试、文档共用。

### 2. 新增独立 formal audit runner，而不把单窗口 audit 改成多态编排器

新 runner 只做这几件事：

1. 遍历固定三窗口
2. 调用现有 `audit_pams_ohlcv_daily_v2.run_update`
3. 将每个窗口的 summary 写入子目录
4. 输出总汇总 `summary.json`

原因：

- 代码最小
- 不污染单窗口 audit 的职责
- 便于直接挂到 `data_refresh` target 和 `full_backfill` 最后一步

### 3. `full_backfill` 新增 `audit_formal_windows` 步骤

保留原有 `audit_full_window`，新增 `audit_formal_windows` 放在其后。

原因：

- `audit_full_window` 仍是单独有价值的全窗口产物
- formal runner 会额外产出 `2016-2026` 和 `2012-2017`
- 兼容既有输出目录结构，同时把三窗口制度化

### 4. formal audit 汇总只负责“是否补齐”，不直接替代单窗口 gate

formal runner 总汇总建议输出：

- `required_windows`
- `windows[]`
- `formal_windows_complete`
- 每个窗口的 `summary_json`
- 每个窗口的 gate 摘要

它不尝试改变 `audit_pams_ohlcv_daily_v2` 内部的 `can_promote_shadow` 判定；只是把三窗口结果固定沉淀下来。

## Implementation Plan

1. 在 `v2_common` 定义 formal audit windows 常量。
2. 新增 `run_pams_ohlcv_daily_v2_formal_audits.py`。
3. 将新 runner 挂到 `data_refresh` target。
4. 更新 `run_pams_ohlcv_daily_v2_full_backfill.py`，追加 `audit_formal_windows` 步骤。
5. 新增/更新单测。
6. 更新 gate spec 与 runbook。
7. 实际跑三窗口 formal audits，产出正式结果。

## Risks / Trade-offs

- 新增 formal runner 后，`full_backfill` 总时长会增加。
- `2012-2017` 取代 `2007-2017` 是正式规则变更，必须在 spec 和文档中写死，不能只靠口头约定。
- 若未来还想调整窗口，只能再次改常量和 spec，这是有意约束。

## Migration Plan

1. 先上线窗口常量和 formal runner。
2. 更新 full backfill 计划与 CLI target。
3. 补跑三窗口 formal audit。
4. 用总汇总确认：
   - `2016-2026`
   - `2012-2017`
   - `2007-2026`
   都已生成产物。

## Rollback

- 删除 formal runner 和其 CLI target。
- 从 `full_backfill` 中移除 `audit_formal_windows` 步骤。
- 将 gate spec 中的 `2012-2017` 改回旧窗口。
- 旧的单窗口 audit 脚本无需回退。
