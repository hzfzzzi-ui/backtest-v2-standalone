## Context

2026-05-08 容器内 baseline regression 已完成但返回 `FAIL`。排查结果显示：

- 股票 sleeve 不漂移，`stock_nav` 与旧锚点一致。
- ETF sleeve 从 `2015-01-20` 开始漂移，首个分歧来自 `sh510300` 分红事件。
- 当前数据包的 ETF 分红事件从旧锚点的 4 行扩展为 37 行。
- 候选实验 `exp_20260508_124555553_fabd` 使用显式分红应收/到账现金流，旧锚点 `exp_20260426_005716047_8650` 不包含对应现金事件输出。

该变更是 baseline 口径确认和重锚，不是策略收益优化。

## Goals / Non-Goals

**Goals:**

- 将 ETF 显式分红现金流确认为当前正式 stock+ETF baseline 口径。
- 注册新 live baseline，使 baseline regression 的 truth 指向包含 ETF 分红现金事件的新候选实验。
- 保留旧 baseline 为 replay/audit anchor，确保可回滚和可解释。
- 记录本次差异的事实证据，包括首个分歧日、分歧标的、现金事件行数和核心指标变化。

**Non-Goals:**

- 不修改股票层信号、ETF 选择逻辑、成交时点、排序主因子或组合构建逻辑。
- 不为了提高收益调整参数。
- 不删除旧实验产物。
- 不把 `outputs/` 内产物逻辑上移为源码实现。

## Decisions

1. 新口径以候选实验 `exp_20260508_124555553_fabd` 为 baseline truth。

   原因：该实验已在容器中完整生成，失败原因已定位为 ETF 分红现金事件数据补齐后的可解释口径变化。替代方案是恢复旧数据快照复现旧 baseline，但用户已明确接受新口径。

2. 旧锚点降级为 replay/audit anchor，而不是删除。

   原因：旧锚点仍是解释本次口径迁移和回滚的必要证据。删除会破坏可审计性。

3. 重锚后必须再跑一次容器内 baseline regression。

   原因：接受新口径只有在新 baseline 能对自身通过回归门禁后才算完成。只更新登记文件但不验证，会留下 compare truth 与产物不一致的风险。

4. 本次不改策略核心代码。

   原因：显式 ETF 分红现金事件能力已经存在，当前问题是正式 baseline truth 未更新，而不是实现缺失。

5. baseline regression 的交易产物比较忽略 `component_exp_id`。

   原因：`component_exp_id` 是每次 rerun 生成的组件实验 ID，属于运行期 provenance，不代表交易语义变化。交易比较仍必须覆盖其他字段的语义 hash，以防实际成交字段、原因码或 meta 发生漂移。

## Risks / Trade-offs

- [Risk] 新 baseline 指标优于旧 baseline，容易被误解为收益优化。
  → Mitigation: 迁移说明必须明确原因是 ETF 分红现金流口径补齐，不是策略逻辑优化。

- [Risk] 当前数据库仍是 mutable source，未来数据补齐可能再次导致 baseline 漂移。
  → Mitigation: baseline 记录必须绑定 `linked_exp_id` 和执行合同；后续应补充独立数据快照或数据版本锁定能力。

- [Risk] 忽略 `component_exp_id` 可能掩盖组件来源变化。
  → Mitigation: 仅在 `portfolio_trades.csv` 的交易语义比较中忽略该字段；组件来源仍由 `run_meta`、执行合同和 manifest 进行约束。

- [Risk] 旧 replay anchor 与新 live baseline 同时存在，展示层可能误读。
  → Mitigation: active baseline 只能有一个；旧锚点必须显式标记为 superseded/replay/audit。

- [Risk] 分红现金事件只覆盖当前 ETF 正式池的一部分历史事件。
  → Mitigation: 本次接受的是当前数据包事实，不扩大声明为全市场分红数据已完整。

## Migration Plan

1. 确认候选实验 `exp_20260508_124555553_fabd` 的 `baseline_compare_status = FAIL` 仅由新口径相对旧锚点造成。
2. 将 `CN_STOCK_ETF_FORMAL_V1` 的 active baseline truth 切换到 `exp_20260508_124555553_fabd`。
3. 将旧锚点 `exp_20260426_005716047_8650` 标记为 replay/audit anchor。
4. 在容器内重跑 baseline regression，确认新 baseline 对自身比较通过。
5. 若新 baseline 无法对自身通过，则回滚 baseline 注册文件，恢复旧 active baseline，并保留候选实验作为 rejected candidate。

## Open Questions

- 是否需要为 `pit_cn_etf_dividend_events` 增加独立快照归档能力。本次不实现，但后续建议作为数据治理任务推进。
