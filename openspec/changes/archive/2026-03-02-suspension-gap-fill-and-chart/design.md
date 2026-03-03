## Context

个股序列 API (`/series/symbol`) 直接把 `pams_ohlcv_daily` 的稀疏结果返回给前端。如果某股票长期停牌（如 sh600099 在 2015-04-15 ~ 2015-12-30 重大资产重组停牌），数据库中无行记录，前端两个数据点之间直线连接，呈现虚假的"匀速上涨"曲线。

现有资源：
- `PostgresDataProvider.load_trading_calendar_cn(start, end)` 可获取交易日历（`pg_provider.py:249`）
- `MarketStateOverlay` / `MarketStatePaneView` 已实现 lightweight-charts 背景蒙版渲染模式（`charts.js:132-169`）
- 个股模式下 K 线已正常渲染（`charts.js:286-298`），折线用橙色（`charts.js:305`）

## Goals / Non-Goals

**Goals:**
- 后端 `/series/symbol` 返回日期连续的序列，停牌日用最后交易日价格 forward-fill，并标记 `suspended: true`
- 前端个股模式下，停牌期间折线用灰色渲染（平线），复牌后恢复正常橙色
- 背景蒙版保留给 MarketStateOverlay（大盘走势），停牌只用线条颜色区分

**Non-Goals:**
- 不修改引擎层数据矩阵（引擎信号计算已自行 ffill，交易层 NaN 已正确跳过）
- 不修改 benchmark 序列端点（指数不存在停牌问题）
- 不补数据库中的缺失行（数据源层面的修复超出本次范围）

## Decisions

### D1: 后端 API 层填充，不改数据库

在 `/series/symbol` 端点内用交易日历做 reindex + ffill，而不是在数据采集层补行。

**理由**：
- 引擎层已有自己的 ffill 策略（只填 close 给 MA 计算），改数据库会影响全局
- API 层填充只影响图表展示，最小化影响范围
- 交易日历已有现成方法 `load_trading_calendar_cn()`

### D2: API 返回 `suspended` 布尔标记

每个 point 新增 `suspended` 字段（默认 `false`，填充日为 `true`）。前端根据此字段切换渲染方式。

**响应格式变更**：
```json
{
  "points": [
    {"date": "2015-04-14", "nav": 1.05, "open": 1.04, "high": 1.06, "low": 1.03, "close": 1.05, "suspended": false},
    {"date": "2015-04-15", "nav": 1.05, "open": 1.05, "high": 1.05, "low": 1.05, "close": 1.05, "suspended": true},
    ...
  ]
}
```

### D3: 停牌折线灰色 + K 线横线，背景蒙版保留给大盘走势

- K 线：停牌日 OHLC 全部填充为同一个 close 值 → K 线自然呈现为横线（无实体无影线）
- 折线颜色：lightweight-charts LineSeries 不支持逐段变色，改用两条 LineSeries 叠加——正常段用橙色 `#f59e0b`，停牌段用灰色 `#999`。将数据按 suspended 拆分成两组 series，非覆盖区域填 NaN（不绘制）
- 背景蒙版：**不新建** SuspensionOverlay。`MarketStateOverlay` 继续渲染大盘走势颜色带，两者互不干扰

### D4: 折线在停牌期间自然变为平线

forward-fill 后 nav 值连续相同 → 折线自然画平线，无需额外处理。

## Risks / Trade-offs

- **额外 DB 查询**：`load_trading_calendar_cn()` 每次调用查一次 `DISTINCT trade_date`，对于单次个股查询增加约 50ms。可接受（非热路径）。
- **首日 close 归一化基准不变**：填充的停牌日 close 与最后交易日相同，归一化后 nav 也相同，不影响基准值。
- **lightweight-charts 不支持逐段变色**：LineSeries 颜色是全局设置。用两条 series（橙色正常段 + 灰色停牌段）叠加实现分段变色，每条 series 在非覆盖区域用 NaN 断开。
