## 1. Governor 标签合同拆分

- [x] 1.1 在 Governor 预算快照中拆分真实 breadth 限仓和 ETF sleeve slot-cap 限仓，新增最小来源字段且不改预算数值。DoD: `cn_etf` 新快照不再把 ETF slot-cap 误报为 `BREADTH_CAP_ACTIVE`；验证: Governor 相关单测 + diagnostics fixture；风险: 旧诊断仍依赖历史 reason code。
- [x] 1.2 在 `day_controls` / ETF provider 之间传递 slot-cap 生效标记和来源文本，确保 Governor 不再猜来源。DoD: `cn_etf` 日级快照能直接读取 slot-cap 来源；验证: 单测覆盖 `state_slot_cap_fallback` 与 `phase1_targets`；风险: 来源字段与 provider 实际 target-selected-count 来源漂移。

## 2. Diagnostics 与回归

- [x] 2.1 更新 zero-trade diagnostics 和相关摘要文案，改为识别新的 ETF slot-cap 标签而不是旧的 breadth 误标签。DoD: rootcause 摘要不再把 ETF slot-cap 写成 breadth 根因；验证: diagnostics 单测；风险: 历史产物与新产物口径并存。
- [x] 2.2 补充回归测试，覆盖 breadth 未启用、ETF slot-cap 生效和二者同时生效三种场景。DoD: 相关单测全部通过；验证: `pytest`；风险: 只测标签未测快照字段完整性。
