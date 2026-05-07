# 2026-04-12 stock sleeve factor research summary

## 1. 结论

当前个股研究应这样理解：

1. 个股主线不是靠简单横截面 rank 因子赚钱。
2. 当前真正还值得继续研究的，只剩 `monthly_divergence_rate`、`volume_price_quality_score`、`pre_profit_failure_context_risk` 三条线。
3. 其中只有 `monthly_divergence_rate` 在研究面上持续表现为明确正向；但它还没有成立的 runtime 接法。
4. 当前个股主线更像“状态过滤 + 少数质量项 + 持有期管理 + 退出管理”的系统，不是“强因子排序系统”。

## 2. 锚点口径更正

这里必须明确区分两个锚点：

### 2.1 个股腿研究参考锚点

- `exp_20260410_171924818_a221`
- `CAGR = 16.38%`
- `Sharpe = 0.7671`
- `MaxDD = -32.48%`
- `Calmar = 0.5042`

这只是 **stock-only 个股腿参考锚点**，用于个股因子研究与局部 A/B。

它不是：

- 组合正式基线
- 系统主线基线
- 多资产组合收益锚点

### 2.2 组合正式锚点

- `A_STOCK_ETF_V1`

2026-04-13 重新按当前运行入口重跑组合后：

- 组合基线重跑：
  - `exp_20260413_050639413_6eef`
  - `perf.json = C:\\Users\\hzfzzzi\\openclaw\\backtest_V2_standalone\\outputs\\experiments\\exp_20260413_050639413_6eef\\perf.json`
  - `CAGR = 12.42%`
  - `Sharpe = 0.4676`
  - `MaxDD = -34.14%`
  - `Calmar = 0.3639`
- 将 `16.38%` 个股腿接回组合后的实验：
  - `exp_20260413_051231810_0b74`
  - `perf.json = C:\\Users\\hzfzzzi\\openclaw\\backtest_V2_standalone\\outputs\\experiments\\exp_20260413_051231810_0b74\\perf.json`
  - `CAGR = 13.30%`
  - `Sharpe = 0.4908`
  - `MaxDD = -31.39%`
  - `Calmar = 0.4239`

因此，后续如果讨论组合收益，应以 **组合锚点** 为准，不再把 `16.38%` 那版个股腿称为“基线”。

## 3. 统一研究窗口

- `1217 = 2012-01-04 ~ 2017-12-29`
- `1222 = 2012-01-04 ~ 2022-12-30`
- `1226 = 2012-01-04 ~ 2026-03-20`

本文所有“有效 / 无效”均指：

- 研究面结论
- 或基于 stock-only 参考锚点的最小 A/B 结论

默认不等同于组合正式主线已验证有效。

## 4. 当前值得继续的 3 条线

### 4.1 `monthly_divergence_rate`

角色定义：

- 研究层正向候选因子
- 更像中期 `context / strength` 因子
- 不适合直接做 `candidate-layer veto` 或 `tiebreak`

事实：

- 重锚定后的三窗口研究中，`IC20` 持续为正。
- 与 `volume_price_quality_score` 的信息不重复，二者是互补关系。
- 在 `BULL` 环境内解释力更强，但不是 `BULL` 独占。

已证伪的 runtime 接法：

- `bottom20 / bottom30 veto`
- `BULL-only tiebreak`

当前结论：

- 保留研究价值
- 暂不进入主线动作层
- 仅允许继续按 `context` 角色研究

### 4.2 `volume_price_quality_score`

角色定义：

- 当前主线内最干净的正向质量项
- 更像弱质量过滤或二级质量增强
- 不是主排序驱动

事实：

- 在主线拆分项中，它比 `breakout_quality_score` 更稳。
- 与 `monthly_divergence_rate` 组合时，双高分桶明显优于任一单因子高分桶。

当前结论：

- 值得保留
- 只能作为辅助质量项研究
- 不应替代主排序

### 4.3 `pre_profit_failure_context_risk`

角色定义：

- lifecycle / exit 研究线中最值得保留的对象
- 表示“利润尚未建立前的失败脆弱性”

事实：

- 在第二版 lifecycle 研究里，它是唯一稳定同号的 lifecycle 风险项。
- `candidate-layer` A/B 已证实：它不属于买入候选层。
- `holding_exit -> exit_candidate` 已证实：这版动作过强，结果明显负向。
- 修正后的 `watch` 审计面已经可靠，且严格 no-op。

当前结论：

- 只能继续做 research-only 审计与命中对象分析
- 不建议直接推进为动作因子
- 更像“风险切换期的早期脆弱提示”

## 5. 当前不值得继续按主因子推进的线

以下对象当前应判定为不适合作为正向主因子推进：

- `breakout_distance`
- `residual_strength`
- `trend_quality`
- `final_score`
- `breakout_quality_score`
- `weak_carry_risk`

共性问题：

- 研究面不稳
- 或方向不对
- 或在更干净锚点下结论翻转

## 6. 当前只适合保留为条件 / 解释层的线

这些对象不是完全没信息，但当前不适合继续按 alpha 因子推进：

- `Risk Gate`
- 负向条件上下文线
- 执行压力线
- 行业二阶段线
- `break_floor_risk`
- `risk_off_exit_context_risk`

当前最合理的处理方式：

- 保留解释价值
- 暂停投入主研究预算

## 7. runtime 接法的阶段性结论

### 7.1 已证伪

- `monthly_divergence_rate -> candidate veto`
- `monthly_divergence_rate -> tiebreak`
- `pre_profit_failure_context_risk -> candidate veto`
- `pre_profit_failure_context_risk -> holding_exit -> exit_candidate`

### 7.2 已修正

- `pre_profit_failure_context_risk -> holding_exit -> watch`
  - 现在已经是严格 no-op
  - 有真实命中
  - 不改变交易路径

### 7.3 尚未成立

截至目前，还没有一条新个股研究因子，已经同时通过：

- 研究面正向
- runtime 最小 A/B 正向

这两个门槛。

## 8. 对当前个股主线的最准确解释

当前个股主线更接近：

- 状态过滤
- 少数质量项帮助筛选
- 持有期赢家贡献收益
- 退出管理决定结果形状

而不是：

- 一组强横截面 rank 因子直接驱动买卖

所以后续研究纪律必须是：

1. 先定义因子角色
2. 再决定允许插入的策略层
3. 不再把任何“有点正向”的对象直接塞进 `candidate layer`

## 9. 当前建议的优先级

### 继续做

1. `monthly_divergence_rate` 的 `context` 角色研究
2. `volume_price_quality_score` 的辅助质量角色研究
3. `pre_profit_failure_context_risk` 的 `watch` 命中对象研究

### 暂停做

1. 新的 `candidate-layer veto / tiebreak`
2. 新的 `exit_candidate` 直接动作实验
3. 对弱线继续盲拆

## 10. 一句话总收口

当前个股研究已经把方向收得很窄：

**真正还值得继续投研究预算的，只剩 `monthly_divergence_rate`、`volume_price_quality_score`、`pre_profit_failure_context_risk` 三条线；其中前两条偏 `context / quality`，第三条偏 `lifecycle warning`。截至目前，还没有一条能直接升成新的个股主线动作因子。**
