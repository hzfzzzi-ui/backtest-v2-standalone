## 1. Static audit

- [x] 1.1 确认当前股票腿基线、最近 V4 stock leg exp id 和三窗口对照 exp id。
- [x] 1.2 审计现有 breakout/ranking 代码，确认最小插入点是候选排序还是下单权重。
- [x] 1.3 确认 `r2_60`、`slope60`、`ret60_vol_adj`、`ret60_dd_adj` 均可在入场前由运行期数据计算。

## 2. Implementation

- [x] 2.1 新增默认关闭的 `trend_quality_soft_score_enabled` 配置。
- [x] 2.2 实现首轮候选方案：趋势质量软评分只影响股票腿新买入候选排序或轻微仓位折扣。
- [x] 2.3 记录运行期审计字段：启用状态、因子权重、候选重排/降权计数。
- [x] 2.4 添加关闭时行为等价和配置解析测试。

## 3. Validation

- [x] 3.1 本地 dry-run 验证配置可解析且关闭行为不变。
- [x] 3.2 Docker 内运行 `2016-2026` 主窗口 AB。
- [x] 3.3 主窗口已失败，按研究纪律不继续运行 `2012-2017` 硬门槛窗口。
- [x] 3.4 主窗口已失败，按研究纪律不继续运行 `2012-2026` 全周期审计。

## 4. Reporting

- [x] 4.1 输出 `outputs/analysis/trend_quality_soft_score_ab_*` 对比报告。
- [x] 4.2 报告事实、推断和决策，明确是否值得继续。
- [x] 4.3 给出回滚方式和下一轮研究方向。
