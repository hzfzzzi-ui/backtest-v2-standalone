## Context

上一轮我们已经把 `V2 formal audit` 固化成统一 runner，并补齐了：

- `2016-2026`
- `2012-2017`
- `2007-2026`

但当前汇总把三者都放进 `required_windows`，导致 hard gate 与 advisory audit 没有边界。用户现在要求：

- 去掉 `2007-2026` 这个 hard gate
- 继续审计 `critical_exception_rows`

因此这次不应该删除 `2007-2026`，而应该把它降级为显式 advisory window。

## Goals / Non-Goals

**Goals**

- 保留 `2007-2026` 全周期审计产物
- 明确 `2016-2026 / 2012-2017` 才是 hard gate
- 让 formal audit 汇总显式区分 `required_windows` 与 `advisory_windows`
- 基于新的 formal audit 汇总继续拆解 `critical_exception_rows`

**Non-Goals**

- 不修改 `audit_pams_ohlcv_daily_v2.py` 里的 `critical_exception_rows` 计算规则
- 不修改 canonical/runtime row status 规则
- 不在本次变更中直接治理 `critical_exception_rows`
- 不移除 `2007-2026` 的运行与落盘

## Decisions

### 1. `2007-2026` 保留运行，但从 hard gate 移出

formal runner 仍执行全部三窗口，以保留全周期审计视角；但 summary 改成：

- `required_windows = ["2016_2026", "2012_2017"]`
- `advisory_windows = ["2007_2026"]`
- `formal_windows_complete` 只检查 `required_windows`
- `all_windows_complete` 检查全部运行窗口

这样既不丢失全周期参考信息，也不再让 `2007-2026` 单独卡死 hard gate。

### 2. 主 spec 直接写死“两硬一参考”

`cn-stock-v2-audit-gates` 更新为：

- hard gate 只要求 `2016-2026 / 2012-2017`
- `2007-2026` 是全周期参考审计，保留但不阻断 hard gate

### 3. `critical_exception_rows` 继续以 formal audit summary 为入口审

本次不新增新表或新脚本，继续使用已有 summary 里的：

- `critical_exception_rows`
- `exception_breakdown_by_phase`
- `key_exception_drilldown`

来回答：

- 哪一类 issue_type 是当前大头
- 集中在哪个 market_phase
- 优先治理哪条线最有效

## Implementation Plan

1. 在 `v2_common` 中补充 hard gate / advisory window key 常量。
2. 更新 formal runner summary 字段语义。
3. 更新对应单测。
4. 更新主 spec 和 runbook。
5. 重跑 formal audits，生成新 summary。
6. 基于新 summary 拆解 `critical_exception_rows`。

## Risks / Trade-offs

- 风险是用户可能把“移出 hard gate”误读为“可以忽略 `2007-2026`”；所以 runbook 和 summary 必须保留 advisory 标记。
- `formal_windows_complete` 的语义发生变化，必须补 `all_windows_complete`，否则旧字段会产生歧义。
- 这次不会直接减少 `critical_exception_rows`，只会更准确地区分“阻断门槛”和“持续治理 backlog”。

## Rollback

- 删掉 `FORMAL_AUDIT_REQUIRED_WINDOW_KEYS / FORMAL_AUDIT_ADVISORY_WINDOW_KEYS`
- 将 formal runner summary 恢复为三窗口全部进入 `required_windows`
- 将主 spec 改回三窗口全部阻断
- 重跑 formal audits 生成旧语义 summary
