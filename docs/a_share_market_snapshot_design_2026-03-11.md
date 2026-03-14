# 全A股市场快照设计说明（截至 2026-03-10）

## 1. 文档目的

本文档用于固定一条独立于策略回测的「收盘后市场快照」设计线。

目标不是直接改交易逻辑，而是先沉淀一份：

- 可日更
- 可审计
- 可扩展
- 与现有回测主线解耦

的全 A 股市场状态产物，作为后续半自动化研究和日终复盘的统一输入。

当前不做的事：

- 不直接把市场快照字段写进 `baseline_V9.1` 交易逻辑
- 不把市场快照和回测产物混成同一个 schema
- 不在本阶段引入文本情绪、盘中数据、公告 NLP


## 2. 当前阶段结论

### 2.1 事实

- 当前策略主线锚点是 `baseline_V9.1`。
- 当前主线口径已经稳定在「`BREAKOUT45 + residual_only + trailing_activate_profit_pct=0.15`」。
- 当前系统里已经有：
  - `run_meta` / artifacts 产物链
  - stage-pipeline / result bridge
  - A 股日频流动性字段补充基础
- 当前用户后续需求明确为：
  - 先补一份截至 `2026-03-10` 的全 A 股市场情况
  - 后续支持每日收盘后更新市场情况

### 2.2 推断

- 下一步最合理的系统化方向，不是继续口头补充市场评论，而是沉淀一份固定 schema 的 `market_snapshot`。
- 这条链应先作为**研究辅助和日终复盘产物**存在，稳定后再考虑是否进入策略约束。


## 3. 截至 2026-03-10 的市场情况补充

### 3.1 事实

截至 `2026-03-10` 收盘，A 股呈现出明显的高成交、科技制造偏强、中小盘显著强于沪深300的结构。

当日收盘概况：

- 上证综指 `+0.65%`，报 `4123.14`
- 深证成指 `+2.04%`，报 `14354.07`
- 创业板指 `+3.04%`，报 `3306.14`
- 科创综指 `+3.02%`
- 全市场上涨家数超 `4500`
- 两市成交额约 `2.42 万亿元`

来源：

- [2026-03-10 A股收盘概况（新浪转发第一财经）](https://finance.sina.com.cn/jjxw/2026-03-10/doc-inhqnvwn6231358.shtml)

最近一周（`2026-03-02` 至 `2026-03-06`）沪市官方运行情况：

- 上证综指周收盘 `4124`
- 周涨跌幅 `-0.93%`
- 沪市主板周成交额 `46418 亿元`
- 科创板周成交额 `12926 亿元`
- 沪市主板市值 `56.4 万亿元`
- 科创板市值 `112182 亿元`
- 沪股通周交易额 `8061 亿元`

来源：

- [上交所《沪市市场运行情况例行发布（2026-03-02 至 2026-03-06）》](https://www.sse.com.cn/aboutus/mediacenter/conference/c/10811025/files/e399d29b437a40baa14dffcb09e11887.pdf)

中证指数最新 factsheet（发布日期 `2026-02-27`）显示，2026 年初以来风格分化显著：

- 沪深300：年初至今 `+1.74%`，滚动 PE `14.32`，PB `1.45`，1 年波动率 `14.54%`
- 中证500：年初至今 `+15.98%`，滚动 PE `30.77`，PB `2.55`，1 年波动率 `19.91%`
- 中证1000：年初至今 `+12.71%`，滚动 PE `37.02`，PB `2.75`，1 年波动率 `20.92%`

来源：

- [沪深300 factsheet（2026-02-27）](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000300factsheet.pdf)
- [中证500 factsheet（2026-02-27）](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000905factsheet.pdf)
- [中证1000 factsheet（2026-02-27）](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000852factsheet.pdf)

融资融券制度侧，融资保证金比例下限已自 `2026-01-19` 起调整为 `100%`。

来源：

- [上交所《关于调整融资保证金比例的通知》](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/specific/margin/c/c_20260114_10805174.shtml)

### 3.2 推断

截至 `2026-03-10`，A 股更接近以下状态：

- 市场处于高成交活跃区间
- 风格上明显偏中小盘、成长、科技制造
- 赚钱效应扩散较强，但估值与波动都明显抬高
- 这类市场里，单纯看指数趋势不够，需要同时跟踪风格、广度、流动性和情绪


## 4. 市场快照的设计原则

### 4.1 事实

当前系统已存在的正式主链是回测实验产物链，而不是市场日终快照链。

### 4.2 设计原则

市场快照设计必须满足：

1. **收盘后可得**
   - 所有字段默认使用 `t` 日收盘后可观测数据
   - 若后续策略消费，默认只能在 `t+1` 生效

2. **与回测实验解耦**
   - 市场快照单独产出，不混进当前 `run_meta` 主 schema
   - 避免污染 baseline 可比性

3. **先描述、后决策**
   - 第一阶段只做状态记录和可视化
   - 第二阶段才评估哪些字段值得进入策略逻辑

4. **滚动历史口径**
   - 所有 zscore / quantile / relative heat 必须基于历史滚动窗口
   - 不允许全样本归一化

5. **优先官方 / 一手数据源**
   - 指数层：中证指数、交易所
   - 杠杆层：交易所融资融券
   - 北向与跨境：港交所 / 交易所披露


## 5. 建议的最小字段体系

建议分 6 层。

### 5.1 指数层

目的：回答「今天市场方向和大盘趋势如何」

字段建议：

- `sse_composite_close`
- `sse_composite_ret_1d`
- `szse_component_close`
- `szse_component_ret_1d`
- `chinext_close`
- `chinext_ret_1d`
- `csi300_close`
- `csi300_ret_1d`
- `csi500_close`
- `csi500_ret_1d`
- `csi1000_close`
- `csi1000_ret_1d`
- `index_trend_20d`
- `index_trend_60d`

### 5.2 风格层

目的：回答「今天是谁在领涨」

字段建议：

- `style_rel_500_vs_300`
- `style_rel_1000_vs_300`
- `style_rel_chinext_vs_300`
- `style_leader_1d`
- `style_leader_20d`
- `small_mid_large_rank`

最小解释口径：

- 若 `500/1000` 明显强于 `300`，视为成长/中小盘占优
- 若 `300` 相对走强，视为大盘价值/防御占优

### 5.3 广度层

目的：回答「市场是少数龙头拉升，还是赚钱效应扩散」

字段建议：

- `advancers_count`
- `decliners_count`
- `up_down_ratio`
- `limit_up_count`
- `limit_down_count`
- `new_high_20d_count`
- `new_low_20d_count`
- `above_ma20_ratio`
- `above_ma60_ratio`

### 5.4 流动性层

目的：回答「今天的钱多不多，交易有多热」

字段建议：

- `market_amount_total`
- `market_amount_ma20`
- `market_amount_heat = market_amount_total / market_amount_ma20_prev`
- `turnover_rate_market`
- `turnover_rate_market_z252`
- `volume_ratio_market`
- `etf_amount_total`

### 5.5 情绪层

目的：回答「当前市场风险偏好强还是弱」

第一阶段建议用行为型情绪代理，不用文本情绪。

字段建议：

- `breadth_balance`
- `limit_balance`
- `turnover_heat`
- `margin_impulse`
- `northbound_flow_ratio`
- `sentiment_score`
- `sentiment_regime`

最小分数建议：

```text
sentiment_score =
0.4 * z(turnover_heat)
+ 0.35 * z(breadth_balance)
+ 0.25 * z(margin_impulse)
```

状态建议：

- `cold`: 滚动 252 日分位数 <= 20%
- `neutral`: 20% ~ 80%
- `hot`: >= 80%

### 5.6 风险层

目的：回答「当前市场是否进入高波动/高相关/高拥挤」

字段建议：

- `market_realized_vol_20d`
- `market_realized_vol_60d`
- `cross_section_corr_20d`
- `breadth_fragility_score`
- `drawdown_from_60d_high`


## 6. 建议的最小产物

第一阶段建议只产出两个文件：

### 6.1 `market_snapshot.json`

建议路径：

```text
outputs/market_snapshots/YYYY-MM-DD/market_snapshot.json
```

建议最小结构：

```json
{
  "trade_date": "2026-03-10",
  "sources": {
    "indices": "csindex/exchange",
    "breadth": "market_daily",
    "liquidity": "daily_basic",
    "margin": "exchange",
    "northbound": "official"
  },
  "index_layer": {},
  "style_layer": {},
  "breadth_layer": {},
  "liquidity_layer": {},
  "sentiment_layer": {},
  "risk_layer": {},
  "warnings": []
}
```

### 6.2 `market_brief.md`

建议路径：

```text
outputs/market_snapshots/YYYY-MM-DD/market_brief.md
```

它是给前端和人工复盘看的摘要版，内容不宜太长，建议固定成：

- 今日结论
- 指数与风格
- 广度与成交
- 情绪状态
- 风险提示


## 7. 每日收盘后半自动化流程

建议第一版流程如下：

```text
T日收盘
  -> 拉取指数与全市场日频数据
  -> 拉取 daily_basic / 融资融券 / 北向等慢变量
  -> 计算 6 层字段
  -> 写 market_snapshot.json
  -> 渲染 market_brief.md
  -> 前端读取并展示
```

建议先不要做的事：

- 不直接触发自动交易
- 不直接写入回测 baseline 产物
- 不直接把 `sentiment_score` 当买卖信号


## 8. 与现有系统的衔接建议

### 8.1 事实

现系统已有以下适合挂接的位置：

- `run_meta` / artifact 体系
- `backtest_v2_artifacts` 汇总逻辑
- stage-pipeline 的日级结果桥接
- A 股 daily basic / liquidity 字段链

### 8.2 推断

但市场快照不应直接写进当前 `run_meta.json`。

建议先独立于实验产物链，原因：

- 防止回测 schema 污染
- 防止 baseline 可比性漂移
- 便于以后单独做“每日收盘后市场总览”页面


## 9. 审计边界

市场快照虽不是交易信号，但仍需遵守研究纪律。

必须检查：

1. 所有字段是否为 `t` 日收盘后可见
2. 是否存在全样本归一化
3. 是否混用不同日历
4. 融资融券、北向、投资者数等字段是否按**发布日期可见**
5. 官方源缺失时是否显式记录 `warnings`

禁止：

- 用未来修订值回填历史
- 用全样本均值或全样本分位数直接标准化
- 用 `t` 日盘后数据去解释 `t` 日盘中策略行为


## 10. 推荐的推进顺序

### 阶段 1：市场快照字段固化

只做：

- schema
- 数据源映射
- JSON / Markdown 产物

### 阶段 2：前端展示

只做：

- 展示市场快照卡片
- 展示市场简报

### 阶段 3：研究接入

只做探索，不直接改主线：

- `sentiment_regime`
- `liquidity_regime`
- `style_regime`

### 阶段 4：半自动化

在日终数据链稳定后，再接入每日定时运行。


## 11. 当前阶段的执行结论

### 11.1 事实

- 截至 `2026-03-10`，市场处于高成交、广度偏强、风格明显偏中小盘与成长的状态。
- 这类状态对 `BREAKOUT + residual` 型策略是有信息量的。

### 11.2 推断

- 现在最值得做的不是继续手动描述市场，而是沉淀一条可日更的 `market_snapshot` 产物链。
- 这条链第一阶段应定位为**研究辅助基础设施**，而不是策略逻辑本身。


## 12. 参考来源

- [2026-03-10 A股收盘概况（新浪/第一财经）](https://finance.sina.com.cn/jjxw/2026-03-10/doc-inhqnvwn6231358.shtml)
- [上交所《沪市市场运行情况例行发布（2026-03-02 至 2026-03-06）》](https://www.sse.com.cn/aboutus/mediacenter/conference/c/10811025/files/e399d29b437a40baa14dffcb09e11887.pdf)
- [沪深300 factsheet（2026-02-27）](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000300factsheet.pdf)
- [中证500 factsheet（2026-02-27）](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000905factsheet.pdf)
- [中证1000 factsheet（2026-02-27）](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000852factsheet.pdf)
- [上交所《关于调整融资保证金比例的通知》](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/specific/margin/c/c_20260114_10805174.shtml)
