## Why

当前 RegimeRouter 使用单一条件判断市况：benchmark close > MA(regime_ma)，输出二值 regime_on/off。这种粗粒度判断存在两个问题：
1. **频繁假切换**：单一均线交叉在震荡区间频繁翻转，导致 MR 分支引入大量噪声交易和双倍回撤（-31% → -57%）
2. **缺乏层次**：忽视行业和个股自身的趋势状态，所有股票使用同一个 regime 判断，无法区分板块轮动

需要一个连续值、多层次的 Regime Filter，输出 RegimeSignal ∈ [0,1] 替代二值判断，作为信号强度门控层。

## What Changes

- 新增独立的 `RegimeFilter` 模块，实现三层层级趋势过滤器（Market → Sector → Stock）
- 每层计算三个趋势因子（EMA50 斜率、EMA20/60 spread、ADX(14)），经 rolling z-score 标准化 → EMA 平滑 → Sigmoid 门控
- 最终输出 RegimeSignal_i = G_market × G_sector(i) × G_stock(i) ∈ [0,1]
- 新增行业指数数据加载能力（从 pit_index_daily 加载 801xxx.SI 申万行业指数 + pit_industry_history 获取股票-行业映射）
- 新增向量化 ADX 矩阵计算（现有仅标量版本）
- 修改 RegimeRouterSignalProvider 的 regime 判断逻辑，用 RegimeSignal 阈值替代简单均线比较

## Capabilities

### New Capabilities
- `regime-filter-engine`: 三层层级趋势过滤器核心计算引擎（因子计算、z-score、sigmoid 门控、向量化预计算）
- `sector-data-loader`: 行业指数数据加载与股票-行业映射（从 DB 加载 SW L1 行业指数 OHLCV + PIT-safe 行业映射）
- `adx-matrix`: 向量化 ADX(14) 矩阵计算（T×N 矩阵，复用现有标量 ADX 逻辑）

### Modified Capabilities
- `regime-router-vectorize`: RegimeRouterSignalProvider 的 regime 判断从二值均线比较改为连续 RegimeSignal 阈值判断；precompute 阶段新增 RegimeFilter 预计算

## Impact

- **新增文件**: `backend/core/engine_vector/regime_filter.py`（~400-500 行）
- **修改文件**:
  - `backend/core/engine_vector/regime_router_signal_provider.py`（~30 行变更：precompute 调用 RegimeFilter、regime_on 由 RegimeSignal 阈值生成）
  - `backend/core/engine_vector/features.py`（新增 `adx_matrix()` 方法）
  - `backend/core/data/pg_provider.py`（新增行业指数/映射加载方法）
- **数据依赖**: pit_index_daily 中的 801xxx.SI 行业指数日线（已入库 99,126 条）、pit_industry_history 行业映射（已有）
- **配置新增**: RegimeFilter 参数（alpha_m, alpha_sec, alpha_i, zscore_window, ema_smooth_span, regime_threshold）
- **性能约束**: 全向量化 O(N×D) 预计算，日循环中 O(1) 查表，不增加引擎运行时间
