# 干净数据证据重置审计报告（2026-03-08）

## 结论

本轮审计结论明确如下：

1. 旧 `ATR1.0` / `BR35+ATR1.0` 晋级证据包不再可靠，必须废弃，不得继续用于 candidate 晋级或 baseline promotion。
2. 造成旧证据失真的主因不是单一策略参数，而是三类问题叠加：
   - 停牌缺口未完整落库
   - OHLCV parquet 缓存可能继续读取修复前旧数据
   - 持仓 NAV 在缺价日按 `0` 估值，制造假尖刺并改写后续交易路径
3. 在完成数据修复、缓存清理、NAV 估值修正后，三组标准实验的当前结果是：
   - `locked baseline` 最优
   - `ATR1.0` 不通过
   - `BR35+ATR1.0` 不通过
4. 从这一刻起，后续策略研究的起点应切换到新的干净 baseline：
   - `exp_20260307_225748064_f5ce`

注意：
- `exp_20260307_051743747_77d8` 仍然是历史清理工程中的“锁定 baseline 工件”。
- 但对后续策略研究而言，它不再是当前最可信的业绩起点；当前研究起点应改为本报告确认后的干净 baseline。

## 范围

本报告覆盖的证据链条是：

1. 数据缺口证明与回填
2. OHLCV 缓存失效 / 手动清理口径
3. NAV 缺价估值修复
4. 三组标准实验重跑
5. 旧 `ATR1.0` / `BR35+ATR1.0` 证据包失效判定

## 事实

### 1. 数据缺口证明已收口

最终证明结果：

- 证明汇总：`353 proven / 0 uncertain / 0 rejected`
- 涉及 `22` 只股票、`43` 段 gap

证据：

- `outputs/ops/price_gap_proof_20260308_0636_batch3/summary.json`
- `outputs/ops/uncertain_clear_validation_20260308_064520/summary.json`

其中最终 apply 汇总显示：

- `rows_total = 353`
- `already_present = 317`
- `inserted = 36`

这意味着当前 repair plan 范围内的 `353` 条缺口行已全部有独立证明且已入库完成。

证据：

- `outputs/ops/price_gap_apply_20260307_224106/summary.json`

### 2. NAV 假尖刺已被系统性压缩

在修复停牌缺口与缺价估值路径后：

- `|daily_return| >= 10%` 的尖刺数量从 `3 -> 1`
- `|daily_return| >= 5%` 的尖刺数量从 `14 -> 10`

证据：

- `outputs/ops/nav_spike_compare_sz000703q1_20260308_051611/summary.json`

在再进一步接入 NAV 缺价平移估值后：

- `|daily_return| >= 10%` 从 `1 -> 0`
- `|daily_return| >= 5%` 从 `10 -> 8`
- `orders_key_equal = true`

这说明这一步修的是估值路径，不是偷偷改了信号或成交。

证据：

- `outputs/ops/nav_fallback_fix_validation_20260308_061225/summary.json`

### 3. 剩余不确定缺口清零后，路径分叉明显收敛

在最后一批 `uncertain` 清零后：

- `first_diff_date` 后移到 `2017-06-13`
- `max_abs_nav_diff` 收敛到 `3297.25`
- `spike_ge_10_old = 0`
- `spike_ge_10_new = 0`

这说明主导性“掉零估值”问题已基本消失，剩余差异只剩小幅路径微调。

证据：

- `outputs/ops/uncertain_clear_validation_20260308_064520/summary.json`

### 4. 三组标准实验已在干净数据下重跑

标准重跑包：

- `outputs/ops/clean_data_standard_rerun_20260307_230128/summary.json`
- `outputs/ops/clean_data_standard_rerun_20260307_230128/summary.md`
- `outputs/ops/clean_data_standard_rerun_20260307_230128/ab_summary.csv`

重跑前动作：

- 已清除 `/tmp/ohlcv_cache.parquet`
- 已清除 `/tmp/ohlcv_cache.meta.json`

重跑结果：

#### A. locked baseline

- 历史：`exp_20260307_051743747_77d8`
- 当前：`exp_20260307_225748064_f5ce`
- `CAGR 6.35% -> 7.85%`
- `MaxDD -47.18% -> -42.38%`
- `Sharpe 0.36 -> 0.48`
- `Trades 61 -> 77`

#### B. ATR1.0

- 历史：`exp_20260307_171750033_eb7b`
- 当前：`exp_20260307_230102004_c602`
- `CAGR 7.90% -> 5.61%`
- `MaxDD -45.51% -> -53.09%`
- `Sharpe 0.40 -> 0.37`
- `Trades 62 -> 75`

#### C. BR35+ATR1.0

- 历史：`exp_20260307_194430192_e932`
- 当前：`exp_20260307_230115260_c92e`
- `CAGR 10.08% -> 5.01%`
- `MaxDD -41.80% -> -46.26%`
- `Sharpe 0.51 -> 0.36`
- `Trades 73 -> 77`

### 5. T+1 审计口径未被破坏

当前静态契约仍然成立：

- `provider.day_signals(day, i, ctx)`
- `pending[next_day] = [...]`
- `t1_execution_confirmed = true`

证据：

- `outputs/ops/clean_data_standard_rerun_20260307_230128/summary.json`

## 判断

### 1. 旧 ATR / BR35 证据包为什么必须废弃

事实是：

- 旧 `ATR1.0` 与 `BR35+ATR1.0` 的优势，在干净数据下没有复现
- 而且方向性还反过来了：当前最强的是 `locked baseline`

因此合理判断是：

- 旧证据包已经被“缺口数据 + 旧缓存 + 缺价估值”污染
- 旧证据包不能继续承担“晋级依据”的角色

### 2. 当前还能保留什么

可以保留的只有两类东西：

1. 旧实验及其报告，作为取证与追溯材料保留
2. 旧方向的经济假设，作为历史假设保留

不能保留的是：

- “旧绩效结论仍然有效”这个判断
- “ATR1.0 或 BR35 仍是当前主候选”这个判断

## 处置决定

### A. 即刻废弃的旧证据包

以下旧证据包自本报告起视为“仅供取证，不再可用于晋级”：

#### ATR1.0 证据包

- `outputs/experiments/exp_20260307_171750033_eb7b`
- `outputs/experiments/atr_stop_research_20260307_161615/summary.json`
- `outputs/experiments/atr_stop_local_robustness_20260307_161712/summary.json`
- `outputs/experiments/atr_stop_window_check_20260307_161756/summary.json`
- `outputs/experiments/atr_stop_terminal_sensitivity_20260307_162729/summary.json`

#### BR35 证据包

- `outputs/experiments/exp_20260307_194430192_e932`
- `outputs/experiments/breakout_window_research_20260307_190247/summary.json`
- `outputs/experiments/breakout_window35_robustness_20260307_191748/summary.json`

### B. 当前有效的研究起点

从本报告开始，后续策略研究的默认起点改为：

- `exp_id = exp_20260307_225748064_f5ce`
- artifacts root: `outputs/experiments/exp_20260307_225748064_f5ce`

这个起点代表：

- 当前代码
- 当前已回填数据
- 当前缓存失效口径
- 当前 NAV 估值修复口径

### C. 当前不做的事

在新的主线确认前，不做以下动作：

- 不再推进 `ATR1.0` 晋级
- 不再推进 `BR35+ATR1.0` 晋级
- 不再引用旧 `10.08% CAGR` 作为当前可用证据

## 残留问题

当前重跑包里的 candidate 审计状态显示为 `blocked`，但这里的 blocker 主要是 runtime 工件噪音：

- `db.password`
- `sizing.order_value = 0.0`

这不是策略漂移主因，不影响本报告关于绩效翻转的结论；但后续如果还要用这些 rerun 包做 formal candidate 评估，应先把这两个 runtime-only diff 从候选漂移审计里剥离。

## 操作指令

从本报告起，请按以下规则执行：

1. 若讨论当前策略研究主线，只引用：
   - `exp_20260307_225748064_f5ce`
   - `outputs/ops/clean_data_standard_rerun_20260307_230128/*`
2. 若需要追查旧结论来源，可查看旧 `ATR1.0` / `BR35` 证据包，但必须标注：
   - `forensic only`
   - `not promotion-grade evidence`
3. 下一轮研究从干净 baseline 重新开始，不沿旧 `ATR1.0 / BR35` 线继续晋级。
