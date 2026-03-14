# baseline_V9.1 研究黑名单 / 白名单

日期：2026-03-10  
适用范围：`baseline_V9.1` 之后的主线研究筛选  
当前主线：`baseline_V9.1`

## 1. 结论摘要

当前主线应固定在 `baseline_V9.1`。

当前已确认事实：

- `baseline_V9.1` 是当前最佳退出锚点。
- 核心差异是 `trailing_activate_profit_pct = 0.15`。
- 当前主线口径约为：
  - `CAGR 13.33%`
  - `MaxDD -26.50%`
  - `Sharpe 0.664`
  - `Calmar 0.503`
- `BEAR` 全退需要保留。
- `ATR_TRAIL` 需要保留，但只能作为后置利润保护模块。
- `TRANS_DOWN` 残仓保留路线，按当前已经测试过的实现，应整体暂停。

当前最重要的问题定义不是“市场退出要不要改”，而是：

> 个股级趋势退出仍然偏弱，导致 `RISK_OFF_EXIT` 被迫接管过多职责；  
> 同时，新增候选层如果直接与主 breakout 同级竞争，会稀释 `BREAKOUT45 + residual_only` 的主 alpha。

## 2. 当前 baseline 口径

主线配置见：

- [baseline_V9.1 config](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/baselines/baseline_V9_1/config.json)
- [baseline index](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/baselines/index.json)

当前主线的结构性特征：

- 主触发：`BREAKOUT45`
- 主排序：`residual_only`
- 股票池：`HS300 + ZZ500`，`PIT_DYNAMIC`
- 市场过滤：开启
- 风险退出：`trans_down_or_bear`
- 后置 trailing：`activate_profit_pct = 0.15`

## 3. 白名单

以下方向允许继续扩展，且应优先作为后续研究候选。

### 3.1 保留项

- `baseline_V9.1` 作为当前唯一主锚点保留。
- `BREAKOUT45 + residual_only` 作为当前已验证主 alpha 保留。
- `BEAR` 全退保留。
- `ATR_STOP` 作为灾难保护保留。
- `ATR_TRAIL` 作为后置利润保护保留。

### 3.2 可继续研究的方向

- 个股级趋势退出重设计，但必须基于 `baseline_V9.1`，且每轮只做一个主改动。
- 排序 alpha 的补充式增强，但只能做软补充，不能直接重写 `residual_only` 主排序。
- 候选层的补位式扩展，但前提是不能与主 breakout 同级抢前排。

### 3.3 已确认有效的退出结论

- `ATR_TRAIL` 不能从入场后立刻参与。
- `trailing_activate_profit_pct = 0.15` 是当前最好的已验证平衡点。
- 市场退出模块本身不是错的；被证伪的是若干粗糙的 `TRANS_DOWN` 残仓保留实现。

## 4. 黑名单

以下方向在当前证据下应视为暂停，不再优先投入研究回合。

### 4.1 入场 / 触发层

- `BREAKOUT40` 主触发替代 `BREAKOUT45`
- `breakout40 + volume_confirm`
- `entry_confirm_mode = volume_confirm`
- `entry_confirm_mode = volume_ratio_confirm`
- 默认 `pb_reclaim_ma20` 直开
- `pullback_candidates_on` 与 breakout 同级竞争

### 4.2 排序 / 持仓层

- `residual + quality` 直接混成主排序
- 固定 `rank tilt` 的轻量仓位倾斜
- `mf_topk` 细调
- `mf_concentrate_scale` 细调

### 4.3 退出层

- 直接关闭 `ATR_TRAIL`
- 当前路径下把 `LOW10` 当成主趋势退出抓手
- `LOW10` 相关单独开关实验
- 当前参数下的 `MA20` 分段趋势退出
- 继续细调 `high_profit_pct`

### 4.4 `TRANS_DOWN` 残仓保留整条路线

当前以下实现已连续证伪，应整体暂停：

- fixed partial
- `trans_down_only partial`
- `first_trans_down_then_full`
- `freeze new entry`
- `top-K trim`
- `residual floor`
- `residual + profit`
- `residual + MA20`

## 5. 灰名单

以下方向不是被完全证伪，而是当前阶段信息量不足、链路不够干净、或未真正打到主瓶颈。

- `score_threshold`
- `industry_cap`
- `cooldown_days`
- `quality` 作为 tie-break
- `pullback` 补位层

重新进入候选池的前提：

- 执行链真实消费该变量；
- 或实现范式发生变化，不再重复旧实验的失败结构。

## 6. 已经比较稳的研究结论

以下结论可以直接作为后续研究纪律使用：

1. 主线 alpha 的核心仍然是 `BREAKOUT45 + residual_only`。
2. `BEAR` 全退不能轻易拿掉。
3. 当前最有效的退出优化，不是进一步改市场退出，而是让 `ATR_TRAIL` 后置启用。
4. `LOW10` 当前在 live path 里基本休眠，不应继续作为主抓手。
5. `TRANS_DOWN` 残仓保留路线，至少按现有实现，都没有成立。
6. 新增候选层如果与主 breakout 同级竞争，容易稀释已验证主 alpha。
7. 把 `quality` 直接并入主排序，当前会破坏已验证的残差趋势 alpha。

## 7. 运行规则

后续所有实验默认遵守以下规则：

1. baseline 统一使用 `baseline_V9.1`。
2. 每轮只做一个主改动。
3. 入场、排序、退出、仓位不要同时改。
4. 先审计通过，再看收益。
5. 若方向属于黑名单，除非实现范式变化，否则不再重复测试。
6. 若方向属于灰名单，必须先说明为什么这次与之前不同。

## 8. 后续推荐的优先顺序

如果继续探索，优先级建议如下：

1. 个股级趋势退出的结构性重设计  
目的：让趋势退出真正承担“趋势结束确认”，继续减轻 `RISK_OFF_EXIT` 的接管程度。

2. 排序 alpha 的软补充  
目的：在不重写 `residual_only` 主排序的前提下，提升持仓质量。

3. 候选层的补位式扩展  
目的：只补空槽，不抢主 breakout 的前排。

## 9. 不建议继续做的事情

以下行为当前应避免：

- 再次把默认 `pullback` 直开后与 breakout 同级竞争
- 再次把 `quality` 直接混进主排序
- 再围绕 `TRANS_DOWN` 保留残仓做参数微调
- 再做 `BREAKOUT40` 或更强入场确认
- 再回到固定比例 partial 风险退出

## 10. 一句话执行口径

后续实验默认从白名单中选；  
黑名单方向暂停；  
灰名单只有在“链路打通”或“实现范式改变”后才允许回到候选池。
