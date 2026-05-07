## 1. Holding/exit hook 接线

- [x] 1.1 新增 research-only holding/exit fragility hook 接口，并限制其只作用于已持仓股票；DoD：hook 在运行时只能接收当前持仓对象，配置若尝试接入 candidate layer 会被拒绝或标记无效；验证：最小单测覆盖“已持仓可接入、候选层不可接入”；风险：边界没锁死会再次把 lifecycle 因子误接回 candidate layer。
- [x] 1.2 为 hook 增加单因子单动作映射能力；DoD：研究配置可以只指定一个 lifecycle fragility 因子和一个 research-only 动作映射；验证：最小配置运行可生成 hook 输入；风险：动作映射过早做成策略默认行为。

## 2. 审计产物

- [x] 2.1 扩展日级诊断，记录 holding/exit fragility hook 的启用状态、覆盖持仓数、命中高风险持仓数和建议动作计数；DoD：实验产物含有完整日级诊断字段；验证：检查单次实验 `portfolio_daily.csv`；风险：只有 perf 没有作用面，会再次出现假实验。
- [x] 2.2 新增持仓级审计产物，记录 symbol、entry 日期、持仓天数、风险分位、命中动作和后续退出标签；DoD：实验产物可逐笔解释 fragility hook 命中对象；验证：检查持仓级审计文件；风险：字段不足以解释生命周期风险。

## 3. 最小 A/B 运行面

- [x] 3.1 基于当前认可的 stock-only 基线，新增 holding/exit fragility 最小 A/B 入口；DoD：能够以“基线 vs 单因子单动作”运行一轮 stock-only 实验；验证：实际跑通一组 A/B；风险：又混入其他因子或其他资产腿。
- [x] 3.2 用 `pre_profit_failure_context_risk` 跑第一轮 holding/exit layer A/B，并回填结果与边界；DoD：生成可审计的结果产物并在 notes 中说明结论只代表这版插入点；验证：检查 A/B 结果与 OpenSpec 状态；风险：把研究面结论误写成主线有效结论。
