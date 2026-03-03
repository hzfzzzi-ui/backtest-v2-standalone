## Context

当前 RegimeRouter 的 regime 判断使用单一均线比较（`bench_close > bench_ma(60)`），输出全局二值 bool。参数扫描实验表明，MR 分支虽增加 +8.6% 收益，但回撤从 -31% 翻倍到 -57%，根本原因是粗粒度 regime 判断导致大量非趋势状态被误判为趋势或反之。

用户设计了三层层级趋势过滤器（Market → Sector → Stock），输出连续 RegimeSignal ∈ [0,1]。数据层面，申万 L1 行业指数（31 个 801xxx.SI）已入库 pit_index_daily（99,126 条，2010~2026），行业映射 pit_industry_history 已有 PIT-safe 数据。

## Goals / Non-Goals

**Goals:**
- 实现三层 RegimeFilter，替代二值 regime_on 判断
- 全向量化预计算，不增加日循环运行时间
- 向后兼容：无 RegimeFilter 配置时退回旧逻辑
- 逐股票 regime 判断（不同股票可以走不同模式）
- 提供诊断输出，验证过滤器效果

**Non-Goals:**
- 不修改子策略信号逻辑（SMA/RSI 买卖规则不变）
- 不修改引擎循环、订单执行、成本计算
- 不修改前端 UI（本次纯后端变更）
- 不做参数自动优化（手动调参 + 实验对比）
- 不做回测 A/B 测试框架（通过现有 sweep 实验验证）

## Decisions

### Decision 1: 新增独立模块 `regime_filter.py`

**选择**: 在 `backend/core/engine_vector/regime_filter.py` 中实现 `RegimeFilter` 类

**备选方案**:
- (A) 内联到 `regime_router_signal_provider.py` — 否决：该文件已 527 行，继续膨胀违反单一职责
- (B) 放在 `backend/core/strategies/` — 否决：RegimeFilter 是引擎层矩阵计算，不是策略层逻辑

**理由**: RegimeFilter 是纯计算模块（输入矩阵 → 输出矩阵），独立于策略和引擎循环，放在 engine_vector 下与 features.py 平级最合适。

### Decision 2: ADX 矩阵实现方式

**选择**: 在 `features.py` 中新增 `adx_matrix(high, low, close, period)` 函数，逐列计算 Wilder ADX

**备选方案**:
- (A) 用 pandas ewm(alpha=1/period) 近似 Wilder 平滑 — 否决：ewm 的初始化方式与 Wilder 不同，会产生数值偏差
- (B) 纯 numpy 无循环实现 — 否决：Wilder 平滑是递归定义（prev × (p-1)/p + curr/p），无法纯向量化，必须有列循环

**理由**: 逐列循环但列内用 pandas Series 操作（与现有 `_rsi_matrix` 模式一致），31 个行业指数 + ~800 只股票的列循环开销可控（< 1s）。

### Decision 3: 行业数据加载路径

**选择**: 在 `pg_provider.py` 新增 `load_sector_indices()` 和 `load_industry_mapping()` 方法，通过 experiment_runner → portfolio_builder → signal_provider 传递

**数据流**:
```
experiment_runner.run_experiment()
  → data_provider.load_sector_indices(start, end)  # 新增
  → data_provider.load_industry_mapping(symbols)    # 新增
  → portfolio_builder.run_portfolio_backtest(..., sector_data=..., industry_map=...)
    → portfolio_simulator.run_vector_...(sector_data=..., industry_map=...)
      → RegimeRouterSignalProvider.precompute(sector_data=..., industry_map=...)
        → RegimeFilter.precompute(benchmark, sector_data, stock_mx, industry_map)
```

**备选方案**:
- (A) RegimeFilter 内部直接连 DB — 否决：违反数据层分离，测试困难
- (B) 通过配置文件指定行业数据 CSV — 否决：增加配置复杂度，数据已在 DB 中

**理由**: 复用现有 DataProvider 模式，数据加载在上层完成，计算模块只接收矩阵。

### Decision 4: 行业名→指数代码映射方式

**选择**: 在 `ingest_universe.py` 中新增 `SW_L1_INDEX_MAP` 常量（industry_l1 名称 → 801xxx.SI 代码）

**理由**: 31 个映射稳定不变（申万标准），内置常量最简单可靠。运行时通过 `pit_industry_history.industry_l1` → `SW_L1_INDEX_MAP[l1]` → `sector_close_matrix[:, sec_col]` 完成逐股票行业查找。

### Decision 5: Regime 路由从全局改为逐股票

**选择**: `regime_on` 从 `bool[T]` 变为 `bool[T, N]` 矩阵

**影响**:
- `day_signals()` 的路由逻辑从 `if regime_on[i]:` 改为按股票分组
- 趋势买入候选 = SMA 金叉 ∩ regime_on[i, col]
- MR 买入候选 = RSI 超卖 ∩ ~regime_on[i, col]
- 卖出逻辑不变（根据持仓类型决定，不受 regime 矩阵影响）

**复杂度评估**: `day_signals()` 现有代码已逐股票遍历候选，改为矩阵索引过滤（`candidates[regime_on[i, :]]`）增加约 5 行代码。

### Decision 6: 配置集成方式

**选择**: 在策略配置的 `strategy` 节点新增 `regime_filter` 子对象

```json
{
  "strategy": {
    "name": "regime_router",
    "regime_ma": 60,
    "regime_filter": {
      "enabled": true,
      "alpha_m": 2.0,
      "alpha_sec": 2.0,
      "alpha_i": 2.0,
      "zscore_window": 120,
      "ema_smooth_span": 10,
      "regime_threshold": 0.3,
      "w_slope": 0.4,
      "w_spread": 0.3,
      "w_adx": 0.3
    },
    "trend_strategy": "sma_cross",
    "trend_params": { ... },
    "mr_strategy": "rsi_reversal",
    "mr_params": { ... }
  }
}
```

**理由**: 作为 regime_router 策略的子配置，不污染顶层配置。`enabled: false` 时完全退回旧逻辑。

## Risks / Trade-offs

**[行业数据缺失]** → 部分行业指数（801960 石油石化、801970 环保、801980 美容护理）仅有 2021-12 起的数据，回测 2016~2021 期间这些行业的 Sector 门控默认 1.0（两层降级）。31 个行业中仅 3 个受影响，覆盖率 90%+。

**[ADX 矩阵计算性能]** → Wilder ADX 需逐列递归计算。800 只股票 × 3900 天 ≈ 312 万数据点，预估 < 2s。31 个行业指数 < 0.1s。整体预计算增加 < 3s，在现有 ~3s 基础上仍可接受。

**[逐股票 regime 增加信号碎片化]** → 同一天不同股票走不同模式可能增加换手率。通过 `regime_threshold` 参数控制：阈值越低，趋势模式覆盖面越广，碎片化越少。初始实验用 0.3（偏宽松）。

**[三层乘法导致信号过度衰减]** → 三层 sigmoid 相乘可能使绝大部分股票的 RegimeSignal 都很低。通过调整各层 α 参数控制：α 越小（如 1.0），sigmoid 越平滑，门控值越趋近 0.5，乘积衰减越少。初始实验建议 α_m=2.0, α_sec=1.5, α_i=1.5。

**[向后兼容]** → `regime_filter.enabled = false` 或未配置时完全退回旧逻辑，零风险。现有配置文件无需任何修改即可正常运行。

## Open Questions

- 三因子权重（w_slope=0.4, w_spread=0.3, w_adx=0.3）是否需要通过参数扫描优化？还是先用默认值跑基准？
- Sector 层的 ADX 是否需要使用行业指数的完整 OHLC（含 high/low）？当前行业指数数据有 OHLC，可以直接用。
