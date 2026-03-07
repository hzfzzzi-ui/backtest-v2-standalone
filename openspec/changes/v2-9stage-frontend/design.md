## Context

当前前端 Drawer 为 3 功能面板（Universe / Signal+Composition / Risk&Exit），需要重组为 9 阶段流水线布局，对应 V2 策略的决策漏斗：

```
S1 股票池 → S2 大盘环境 → S3 行业趋势 → S4 个股趋势 → S5 个股排序
→ S6 入场信号 → S7 组合构建 → S8 风险控制 → S9 退出
```

后端 API 编译层（`_experiment_runner_api.py`）已支持全部 9 个阶段的参数编译，包括：
- `signal_generation.strategy = "BREAKOUT_TREND"` → 读取 `signal_generation.breakout` 块
- `stock_trend_filter` → `enable_v2_trend_filter`
- `sector_gate` → `enable_sector_gate`
- `ranking` → `momentum_top_pct`
- `exit_rules.ma20_exit` / `low10_exit` → 已编译

本次改动为**纯前端重组**，不改后端。

## Goals / Non-Goals

**Goals:**
- Rail 从 5 按钮扩展到 11（S1-S9 + JSON + History），每个 Stage 独立面板
- S6 策略选择器新增 BREAKOUT_TREND 和 RSI_REVERSAL
- `buildConfigDraft()` 为新策略生成正确的 config JSON（含 breakout/rsi 参数块）
- `applyConfigToUI()` 能从 breakout/rsi 配置 JSON 回填 UI
- 注册冠军配置到加载下拉，前端跑出结果与 3.4 号脚本一致

**Non-Goals:**
- 不改后端 API 或引擎代码
- 不实现 S3/S5 的后端逻辑增强（已有）
- 不改变 config_json 的 wire format（只补充新字段）

## Decisions

### D1: Rail 按钮布局

11 个按钮垂直排列，S1-S9 使用数字 badge 标识阶段序号：

```
Rail (48px)
┌──────┐
│ ① 池 │ S1 Universe 股票池
│ ② 盘 │ S2 Market 大盘环境
│ ③ 业 │ S3 Industry 行业趋势
│ ④ 股 │ S4 Stock 个股趋势
│ ⑤ 排 │ S5 Ranking 个股排序
│ ⑥ 入 │ S6 Entry 入场信号
│ ⑦ 组 │ S7 Portfolio 组合构建
│ ⑧ 控 │ S8 Risk 风险控制
│ ⑨ 出 │ S9 Exit 退出
│ ── │ (分隔线)
│ {} │ JSON
│ 🕐 │ History
└──────┘
```

每个 Rail 按钮用 `data-panel="s1"` ~ `data-panel="s9"` 对应 module section。

### D2: HTML Section 分配

| Stage | data-module | 来源 | 内容 |
|-------|------------|------|------|
| S1 | `s1` | 现 `universe` | 原样保留，不动任何 HTML |
| S2 | `s2` | 现 `sigcomp > 市况判断` | regime_ma, benchmark regime 开关 |
| S3 | `s3` | **新** | 行业门控：启用开关, rank_window(60), top_pct(30%) |
| S4 | `s4` | 现 `sigcomp > 入场趋势过滤` | 个股趋势：enable, short_ma(20), long_ma(60) |
| S5 | `s5` | **新** | 个股排序：momentum_top_pct(10%), 启用开关 |
| S6 | `s6` | 现 `sigcomp > 趋势模式 + 震荡模式` | 策略选择器 + 参数面板 |
| S7 | `s7` | 现 `risk > Position & Risk 上半` | max_positions, lot, sizing |
| S8 | `s8` | 现 `risk > Position & Risk 下半` | ATR 止损, DD 熔断, MA200 过滤 |
| S9 | `s9` | 现 `risk > Exit` | TP, trail, 信号反转, 时间退出, 持仓约束, MA20退出, LOW10退出 |

### D3: S6 策略选择器

```html
<select id="wbTrendStrategy">
  <option value="SMA_CROSS">均线交叉 SMA</option>
  <option value="EMA_CROSS" selected>均线交叉 EMA</option>
  <option value="BREAKOUT_TREND">突破趋势 Breakout</option>
  <option value="RSI_REVERSAL">RSI 均值回归</option>
</select>
```

选择不同策略时，动态显示/隐藏对应参数面板：

| 选择 | 显示面板 | 隐藏面板 |
|------|---------|---------|
| SMA_CROSS | `wbSigParamsSMA`(fast/slow/buffer) | breakout, rsi |
| EMA_CROSS | `wbSigParamsSMA`(fast/slow/buffer) | breakout, rsi |
| BREAKOUT_TREND | `wbBreakoutParams`(breakout_window, min_price) | sma, rsi |
| RSI_REVERSAL | `wbMrParamsRSI`(period/buy/sell/hold/stop) | sma, breakout |

### D4: buildConfigDraft() 新增字段

```javascript
// S2 大盘环境 — 已有 signal_generation.regime_detection
// S3 行业门控 — 新增 sector_gate 块
sector_gate: {
  enabled: !!byId('wbSectorGate')?.checked,
  rank_window: Number(byId('wbSectorRankWindow')?.value || 60),
  top_pct: Number(byId('wbSectorTopPct')?.value || 30) / 100,
},
// S4 个股趋势 — 新增 stock_trend_filter 块
stock_trend_filter: {
  enabled: !!byId('wbStockTrendFilter')?.checked,
  short_ma: Number(byId('wbStockTrendShortMa')?.value || 20),
  long_ma: Number(byId('wbStockTrendLongMa')?.value || 60),
},
// S5 排序 — 新增 ranking 块到 signal_generation
signal_generation.ranking: {
  momentum_top_pct: Number(byId('wbMomentumTopPct')?.value || 0) / 100,
},
// S6 策略 = BREAKOUT_TREND 时
signal_generation.breakout: {
  breakout_window: Number(byId('wbBreakoutWindow')?.value || 20),
},
// S9 退出 — 新增 ma20_exit, low10_exit
exit_rules.ma20_exit: { enabled: !!byId('wbExitMa20')?.checked },
exit_rules.low10_exit: { enabled: !!byId('wbExitLow10')?.checked },
// universe_filter — 新增
universe_filter: { min_price: Number(byId('wbMinPriceFilter')?.value || 0) },
```

### D5: applyConfigToUI() 反向映射

从 config_json 回填 UI 控件：
- `signal_generation.strategy = "BREAKOUT_TREND"` → 选中 wbTrendStrategy + 显示 breakout 面板
- `signal_generation.breakout.breakout_window` → wbBreakoutWindow
- `stock_trend_filter.enabled` → wbStockTrendFilter
- `sector_gate.*` → S3 面板
- `signal_generation.ranking.momentum_top_pct` → wbMomentumTopPct
- `exit_rules.ma20_exit.enabled` → wbExitMa20
- `exit_rules.low10_exit.enabled` → wbExitLow10

### D6: 冠军配置预置

创建两个 workbench config JSON 文件，使用 `_config_store.py` 的格式：

**Breakout 冠军**（3.4 号 P3-D）：
```json
{
  "strategy_pack": "BREAKOUT_TREND",
  "signal_generation": { "strategy": "BREAKOUT_TREND", "breakout": { "breakout_window": 20 } },
  "stock_trend_filter": { "enabled": false },
  "exit_rules": {
    "atr_stop": { "enabled": true, "k": 1.5 },
    "trailing": { "enabled": true, "k": 3.0 },
    "take_profit": { "enabled": true, "mode": "pct", "pct": 0.20 },
    "low10_exit": { "enabled": true },
    "hold_constraint": { "min_hold_days": 5, "cooldown_days": 5 }
  },
  "position_risk": {
    "max_positions": 10,
    "risk_budget": { "enabled": true, "dd_reduce_pct": 0.10, "dd_reduce_scale": 0.5, "atr_stop_k": 1.5 }
  }
}
```

**EMA 冠军**（G5）：config 已在 run_ab_compare.py 中定义。

验证标准：从前端加载配置 → 运行 → Breakout CAGR +5.46%, MDD -24.32%。

### D7: CSS 适配

Rail 区域需要容纳 11 个按钮。现有 Rail 已用 flex-column 布局，按钮间距需缩小。S1-S9 按钮使用带数字的 badge 风格而非 SVG 图标。JSON 和 History 保留原 SVG 图标，用分隔线与 S1-S9 区分。

## Alternatives Considered

1. **Tab 横排**：9 个 tab 水平排列会太挤。垂直 Rail 更适合。
2. **折叠面板而非 Rail**：保持一个面板内用 `<details>` 折叠 9 段。但信息密度太高，不如独立面板清晰。
3. **动态 Rail（只显示启用的阶段）**：增加复杂度，不值得。
